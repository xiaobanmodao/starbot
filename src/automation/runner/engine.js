import { runWatcher } from '../watchers/index.js';
import { runAction } from '../actions/index.js';
import { addResult } from '../store/results.js';
import { clearDaemonState, setDaemonRunning } from '../store/daemon_state.js';
import { listTasks, updateTask } from '../store/tasks.js';
import { notifySystem } from '../notifier/system.js';
import { runAIDecision, shouldTriggerAIDecision } from '../ai/decision.js';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nowMs() {
  return Date.now();
}

function due(task) {
  const intervalMs = Math.max(1, Number(task.interval_sec) || 1) * 1000;
  const last = task.last_run_at ? Date.parse(task.last_run_at) : NaN;
  if (!Number.isFinite(last)) return true;
  return nowMs() >= last + intervalMs;
}

function ended(task) {
  if (!task.end_at) return false;
  const end = Date.parse(String(task.end_at));
  if (!Number.isFinite(end)) return false;
  return nowMs() >= end;
}

export async function runTaskCycle(task, cfg = null) {
  if (ended(task)) {
    updateTask(task.id, {
      status: 'completed',
      enabled: false,
      last_run_at: new Date().toISOString(),
      last_status: 'completed',
      last_error: '',
    });
    addResult({
      task_id: task.task_id,
      origin_conversation_id: task.origin_conversation_id,
      event: 'task_completed',
      status: 'ok',
      details: { reason: 'end_time_reached' },
    });
    return;
  }

  const watch = runWatcher(task.watcher);
  if (!watch.matched) {
    updateTask(task.id, {
      last_run_at: watch.timestamp,
      last_status: 'idle',
      last_error: '',
    });
    return;
  }

  const act = runAction(task.action);
  const nextErrorStreak = act.success ? 0 : Number(task.error_streak || 0) + 1;
  const status = act.success ? 'ok' : 'error';
  const event = act.success ? 'file_detected_and_deleted' : 'file_detected_but_action_failed';
  updateTask(task.id, {
    last_run_at: act.timestamp,
    last_status: status,
    last_error: act.error || '',
    error_streak: nextErrorStreak,
  });
  addResult({
    task_id: task.task_id,
    origin_conversation_id: task.origin_conversation_id,
    event,
    status,
    details: {
      watcher: watch,
      action: act,
    },
  });

  if (task.notify) {
    notifySystem(`${task.task_id}: ${event}`);
  }

  const structuredEvent = {
    task_type: 'generic_background_task',
    event_type: act.success ? 'normal_action_result' : 'ambiguous_condition',
    task_id: task.task_id,
    timestamp: act.timestamp,
    context: {
      watcher: watch,
      action: act,
      error_streak: nextErrorStreak,
      metrics_conflict: false,
      unknown_pattern: !act.success && /unknown|denied|busy|lock/i.test(String(act.error || '')),
      environment: process.env.NODE_ENV || 'prod',
    },
    decision_required: task?.ai_think_when?.decision_required || 'classify',
  };

  if (!shouldTriggerAIDecision(task.ai_think_when, structuredEvent)) return;

  const decision = await runAIDecision(cfg || {}, structuredEvent);
  updateTask(task.id, { ai_last_decision: decision });
  addResult({
    task_id: task.task_id,
    origin_conversation_id: task.origin_conversation_id,
    event: 'ai_decision_generated',
    status: 'ok',
    details: decision,
  });

  const rec = String(decision?.analysis?.recommended_action || '').toLowerCase();
  if (rec === 'ignore') {
    updateTask(task.id, { enabled: false, status: 'completed' });
  } else if (rec === 'wait') {
    updateTask(task.id, { last_status: 'idle' });
  } else if (rec === 'escalate' && task.notify) {
    notifySystem(`${task.task_id}: ai_escalate`);
  }
}

export async function runAutomationDaemon(cfg = null) {
  setDaemonRunning(process.pid);
  let stop = false;
  const running = new Set();
  const shutdown = () => { stop = true; };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  console.log('[automation.runner] started');

  while (!stop) {
    const tasks = listTasks().filter((task) => task.enabled && task.status !== 'completed');
    for (const task of tasks) {
      if (running.has(task.id)) continue;
      if (!due(task)) continue;
      running.add(task.id);
      runTaskCycle(task, cfg)
        .catch((e) => {
          updateTask(task.id, {
            last_run_at: new Date().toISOString(),
            last_status: 'error',
            last_error: String(e?.message || e || 'unknown error'),
          });
          addResult({
            task_id: task.task_id,
            origin_conversation_id: task.origin_conversation_id,
            event: 'runner_exception',
            status: 'error',
            details: { error: String(e?.message || e || 'unknown error') },
          });
        })
        .finally(() => running.delete(task.id));
    }
    await sleep(1000);
  }

  clearDaemonState();
  console.log('[automation.runner] stopped');
}
