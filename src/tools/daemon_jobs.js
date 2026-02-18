import { spawn } from 'child_process';
import { join } from 'path';
import { tool } from './registry.js';
import {
  createFileDeleteTask,
  listTasks,
  removeTask,
  updateTask,
} from '../automation/store/tasks.js';
import { loadDaemonState } from '../automation/store/daemon_state.js';

function isPidAlive(pid) {
  const n = Number(pid);
  if (!Number.isFinite(n) || n <= 0) return false;
  try {
    process.kill(n, 0);
    return true;
  } catch {
    return false;
  }
}

function daemonStatus() {
  const state = loadDaemonState();
  const pid = Number(state?.pid || 0);
  const running = isPidAlive(pid);
  return {
    running,
    pid: running ? pid : null,
    started_at: state?.started_at || null,
  };
}

function startDaemonIfNeeded() {
  const current = daemonStatus();
  if (current.running) return current;
  const entry = join(process.cwd(), 'src', 'index.js');
  const child = spawn(process.execPath, [entry, '--daemon'], {
    detached: true,
    stdio: 'ignore',
    cwd: process.cwd(),
  });
  child.unref();
  return { running: true, pid: child.pid, started_at: new Date().toISOString() };
}

tool('unattended_watch_delete_file', 'Create unattended automation task: monitor an absolute file path and delete it as soon as it appears.', {
  properties: {
    task_id: { type: 'string', description: 'Stable task id, e.g. auto_delete_desktop_file' },
    file_path: { type: 'string', description: 'Absolute path to monitor and delete' },
    interval_sec: { type: 'number', description: 'Polling interval in seconds (default 1)' },
    end_at: { type: 'string', description: 'Optional ISO8601 end time; task will auto-complete at this time' },
    system_notify: { type: 'boolean', description: 'Trigger OS notification on each completed delete event (default true)' },
    auto_start_daemon: { type: 'boolean', description: 'Start daemon automatically if not running (default true)' },
  },
  required: ['task_id', 'file_path'],
}, true, async ({ task_id, file_path, interval_sec = 1, end_at = null, system_notify = true, auto_start_daemon = true }, context = {}) => {
  const originConversationId = String(context?.origin_conversation_id || '').trim();
  if (!originConversationId) {
    return JSON.stringify({ ok: false, error: 'origin_conversation_id missing' }, null, 2);
  }
  const task = createFileDeleteTask({
    task_id,
    file_path,
    interval_sec,
    end_at,
    notify: system_notify !== false,
    origin_conversation_id: originConversationId,
  });
  const daemon = auto_start_daemon === false ? daemonStatus() : startDaemonIfNeeded();
  return JSON.stringify({ ok: true, task, daemon }, null, 2);
});

tool('unattended_list_jobs', 'List unattended automation tasks and daemon status.', {
  properties: {},
  required: [],
}, false, async () => JSON.stringify({
  daemon: daemonStatus(),
  jobs: listTasks(),
}, null, 2));

tool('unattended_update_job', 'Update unattended automation task fields.', {
  properties: {
    id: { type: 'string', description: 'Task UUID id' },
    enabled: { type: 'boolean', description: 'Enable or disable this task' },
    interval_sec: { type: 'number', description: 'Polling interval in seconds' },
    system_notify: { type: 'boolean', description: 'Enable or disable system notification' },
  },
  required: ['id'],
}, true, async ({ id, enabled, interval_sec, system_notify }) => {
  const patch = {};
  if (typeof enabled === 'boolean') patch.enabled = enabled;
  if (interval_sec !== undefined) patch.interval_sec = interval_sec;
  if (typeof system_notify === 'boolean') patch.notify = system_notify;
  if (patch.enabled === true) patch.status = 'running';
  const updated = updateTask(id, patch);
  return JSON.stringify({ ok: true, task: updated }, null, 2);
});

tool('unattended_remove_job', 'Remove unattended automation task.', {
  properties: { id: { type: 'string', description: 'Task UUID id' } },
  required: ['id'],
}, true, async ({ id }) => JSON.stringify({ ok: removeTask(id), id }, null, 2));

tool('unattended_daemon_status', 'Check unattended automation daemon status.', {
  properties: {},
  required: [],
}, false, async () => JSON.stringify(daemonStatus(), null, 2));

tool('unattended_daemon_start', 'Start unattended automation daemon.', {
  properties: {},
  required: [],
}, true, async () => JSON.stringify(startDaemonIfNeeded(), null, 2));
