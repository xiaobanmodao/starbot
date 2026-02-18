import { spawn } from 'child_process';
import { join } from 'path';
import { tool } from './registry.js';
import {
  createJob,
  listJobs,
  loadDaemonState,
  removeJob,
  updateJob,
} from '../daemon_store.js';

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

tool('unattended_create_job', 'Create a persistent unattended background job. Use when user asks AI to keep doing a task without repeated prompts.', {
  properties: {
    name: { type: 'string', description: 'Short job name' },
    objective: { type: 'string', description: 'Detailed long-running objective' },
    interval_sec: { type: 'number', description: 'Run interval in seconds (default 60)' },
    system_notify: { type: 'boolean', description: 'Trigger OS notification when a run completes (default false)' },
    auto_start_daemon: { type: 'boolean', description: 'Auto start daemon if not running (default true)' },
  },
  required: ['name', 'objective'],
}, true, async ({ name, objective, interval_sec = 60, system_notify = false, auto_start_daemon = true }, context = {}) => {
  const originConversationId = String(context?.origin_conversation_id || '').trim();
  if (!originConversationId) {
    return JSON.stringify({
      ok: false,
      error: 'origin_conversation_id missing; this tool must be called from an active conversation.',
    }, null, 2);
  }
  const job = createJob({
    name,
    objective,
    interval_sec,
    origin_conversation_id: originConversationId,
    enabled: true,
  });
  if (system_notify) {
    updateJob(job.id, { system_notify: true });
  }
  let status = daemonStatus();
  if (auto_start_daemon !== false) status = startDaemonIfNeeded();
  return JSON.stringify({
    ok: true,
    job,
    daemon: status,
    message: 'Unattended job created.',
  }, null, 2);
});

tool('unattended_list_jobs', 'List unattended background jobs and daemon status.', {
  properties: {},
  required: [],
}, false, async () => {
  return JSON.stringify({
    daemon: daemonStatus(),
    jobs: listJobs(),
  }, null, 2);
});

tool('unattended_update_job', 'Update unattended job fields like enabled status, interval, objective, or name.', {
  properties: {
    id: { type: 'string', description: 'Job id' },
    enabled: { type: 'boolean', description: 'Enable/disable job' },
    interval_sec: { type: 'number', description: 'Interval in seconds' },
    system_notify: { type: 'boolean', description: 'Enable/disable OS notification' },
    objective: { type: 'string', description: 'New objective text' },
    name: { type: 'string', description: 'New name' },
  },
  required: ['id'],
}, true, async ({ id, enabled, interval_sec, system_notify, objective, name }) => {
  const patch = {};
  if (typeof enabled === 'boolean') patch.enabled = enabled;
  if (interval_sec !== undefined) patch.interval_sec = interval_sec;
  if (typeof system_notify === 'boolean') patch.system_notify = system_notify;
  if (objective !== undefined) patch.objective = objective;
  if (name !== undefined) patch.name = name;
  const updated = updateJob(id, patch);
  return JSON.stringify({ ok: true, job: updated }, null, 2);
});

tool('unattended_remove_job', 'Delete an unattended background job.', {
  properties: {
    id: { type: 'string', description: 'Job id' },
  },
  required: ['id'],
}, true, async ({ id }) => {
  const ok = removeJob(id);
  return JSON.stringify({ ok, id }, null, 2);
});

tool('unattended_daemon_status', 'Check whether unattended daemon is running.', {
  properties: {},
  required: [],
}, false, async () => JSON.stringify(daemonStatus(), null, 2));

tool('unattended_daemon_start', 'Start unattended daemon process if not running.', {
  properties: {},
  required: [],
}, true, async () => JSON.stringify(startDaemonIfNeeded(), null, 2));
