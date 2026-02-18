import { spawn } from 'child_process';
import { clearDaemonState, listJobs, saveDaemonState, updateJob } from './daemon_store.js';
import { addResult } from './result_store.js';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nowMs() {
  return Date.now();
}

function nextDueAt(job) {
  const interval = Math.max(1, Number(job.interval_sec) || 1) * 1000;
  const last = job.last_run_at ? Date.parse(job.last_run_at) : NaN;
  if (!Number.isFinite(last)) return 0;
  return last + interval;
}

function notifySystem(message) {
  const text = String(message || '').trim();
  if (!text) return;
  if (process.platform === 'win32') {
    const esc = text.replace(/'/g, "''");
    const script = `[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null; [System.Windows.Forms.MessageBox]::Show('${esc}','StarBot Daemon') | Out-Null`;
    const child = spawn('powershell.exe', ['-NoProfile', '-Command', script], {
      detached: true,
      stdio: 'ignore',
    });
    child.unref();
  }
}

async function runJob(job) {
  if (!job.origin_conversation_id) {
    updateJob(job.id, {
      last_run_at: new Date().toISOString(),
      last_status: 'error',
      last_error: 'missing origin_conversation_id; recreate this job from an active conversation',
    });
    return;
  }

  // Runner spec: deterministic and non-LLM.
  // type=heartbeat creates a structured status result only.
  const startedAt = new Date().toISOString();
  const summary = `任务 ${job.name} 执行完成`;
  const payload = {
    job_id: job.id,
    name: job.name,
    objective: job.objective,
    runner_type: 'heartbeat',
    started_at: startedAt,
    completed_at: new Date().toISOString(),
  };

  addResult({
    origin_conversation_id: job.origin_conversation_id,
    job_id: job.id,
    summary,
    payload,
    status: 'completed',
  });

  updateJob(job.id, {
    last_run_at: payload.completed_at,
    last_status: 'completed',
    last_error: '',
  });

  if (job.system_notify) {
    notifySystem(`${job.name}: ${summary}`);
  }
}

export async function runDaemon() {
  const running = new Set();
  let stop = false;
  const shutdown = () => { stop = true; };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
  saveDaemonState({
    pid: process.pid,
    started_at: new Date().toISOString(),
    status: 'running',
  });

  console.log('[daemon] StarBot daemon started.');
  console.log('[daemon] Runner policy: no conversation, no LLM, structured results only.');

  while (!stop) {
    const jobs = listJobs().filter((job) => job.enabled);
    const now = nowMs();

    for (const job of jobs) {
      if (running.has(job.id)) continue;
      if (now < nextDueAt(job)) continue;

      running.add(job.id);
      runJob(job)
        .catch((e) => {
          updateJob(job.id, {
            last_run_at: new Date().toISOString(),
            last_status: 'error',
            last_error: String(e?.message || e || 'unknown error'),
          });
        })
        .finally(() => running.delete(job.id));
    }

    await sleep(1000);
  }

  clearDaemonState();
  console.log('[daemon] Stopped.');
}
