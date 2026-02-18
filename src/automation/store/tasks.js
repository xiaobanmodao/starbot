import { randomUUID } from 'crypto';
import { filePath, nowIso, readJson, writeJson } from './base.js';

const FILE = 'automation_tasks.json';

function readDb() {
  const parsed = readJson(FILE, { tasks: [] });
  const tasks = Array.isArray(parsed?.tasks) ? parsed.tasks : [];
  return { tasks };
}

function writeDb(db) {
  writeJson(FILE, { tasks: Array.isArray(db?.tasks) ? db.tasks : [] });
}

function normalizeAbsPath(path) {
  const text = String(path || '').trim();
  if (!text) return '';
  // Windows absolute path (C:\...) or UNC (\\server\share)
  const isWinAbs = /^[a-zA-Z]:\\/.test(text) || /^\\\\/.test(text);
  // POSIX absolute path
  const isPosixAbs = text.startsWith('/');
  return (isWinAbs || isPosixAbs) ? text : '';
}

function normalizeInterval(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.max(1, Math.min(86400, Math.trunc(n)));
}

export function createFileDeleteTask({
  origin_conversation_id,
  task_id,
  file_path,
  interval_sec = 1,
  end_at = null,
  notify = true,
}) {
  const origin = String(origin_conversation_id || '').trim();
  const taskName = String(task_id || '').trim();
  const absPath = normalizeAbsPath(file_path);
  const interval = normalizeInterval(interval_sec);
  if (!origin) throw new Error('origin_conversation_id is required');
  if (!taskName) throw new Error('task_id is required');
  if (!absPath) throw new Error('file_path must be an absolute path');
  if (!interval) throw new Error('interval_sec must be a positive integer');
  if (end_at && Number.isNaN(Date.parse(String(end_at)))) throw new Error('end_at must be ISO datetime');

  const db = readDb();
  const now = nowIso();
  const task = {
    id: randomUUID(),
    task_id: taskName,
    origin_conversation_id: origin,
    watcher: { type: 'file_exists', path: absPath },
    action: { type: 'delete_file', path: absPath },
    interval_sec: interval,
    end_at: end_at ? String(end_at) : null,
    notify: Boolean(notify),
    status: 'running',
    enabled: true,
    last_run_at: null,
    last_status: 'idle',
    last_error: '',
    created_at: now,
    updated_at: now,
  };
  db.tasks.push(task);
  writeDb(db);
  return task;
}

export function listTasks() {
  return readDb().tasks;
}

export function updateTask(id, patch = {}) {
  const sid = String(id || '').trim();
  if (!sid) throw new Error('id is required');
  const db = readDb();
  const idx = db.tasks.findIndex((item) => item.id === sid);
  if (idx < 0) throw new Error(`task not found: ${sid}`);
  const next = { ...db.tasks[idx] };
  if (Object.prototype.hasOwnProperty.call(patch, 'enabled')) next.enabled = Boolean(patch.enabled);
  if (Object.prototype.hasOwnProperty.call(patch, 'status')) next.status = String(patch.status || next.status);
  if (Object.prototype.hasOwnProperty.call(patch, 'last_run_at')) next.last_run_at = patch.last_run_at || null;
  if (Object.prototype.hasOwnProperty.call(patch, 'last_status')) next.last_status = String(patch.last_status || '');
  if (Object.prototype.hasOwnProperty.call(patch, 'last_error')) next.last_error = String(patch.last_error || '');
  if (Object.prototype.hasOwnProperty.call(patch, 'notify')) next.notify = Boolean(patch.notify);
  if (Object.prototype.hasOwnProperty.call(patch, 'interval_sec')) {
    const n = normalizeInterval(patch.interval_sec);
    if (!n) throw new Error('interval_sec must be a positive integer');
    next.interval_sec = n;
  }
  next.updated_at = nowIso();
  db.tasks[idx] = next;
  writeDb(db);
  return next;
}

export function removeTask(id) {
  const sid = String(id || '').trim();
  if (!sid) throw new Error('id is required');
  const db = readDb();
  const before = db.tasks.length;
  db.tasks = db.tasks.filter((item) => item.id !== sid);
  if (before === db.tasks.length) return false;
  writeDb(db);
  return true;
}

export function tasksFilePath() {
  return filePath(FILE);
}
