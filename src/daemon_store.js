import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import { randomUUID } from 'crypto';

const STARBOT_DIR = join(homedir(), '.starbot');
const JOBS_FILE = join(STARBOT_DIR, 'daemon_jobs.json');
const DAEMON_STATE_FILE = join(STARBOT_DIR, 'daemon_state.json');

function ensureDir() {
  mkdirSync(STARBOT_DIR, { recursive: true });
}

function nowIso() {
  return new Date().toISOString();
}

function normalizeInterval(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.max(1, Math.min(86400, Math.trunc(n)));
}

function normalizeText(value, max = 5000) {
  return String(value || '').trim().slice(0, max);
}

function readDb() {
  ensureDir();
  if (!existsSync(JOBS_FILE)) return { jobs: [] };
  try {
    const parsed = JSON.parse(readFileSync(JOBS_FILE, 'utf-8'));
    const jobs = Array.isArray(parsed?.jobs) ? parsed.jobs : [];
    return { jobs };
  } catch {
    return { jobs: [] };
  }
}

function writeDb(db) {
  ensureDir();
  const safe = { jobs: Array.isArray(db?.jobs) ? db.jobs : [] };
  writeFileSync(JOBS_FILE, JSON.stringify(safe, null, 2), 'utf-8');
}

export function listJobs() {
  return readDb().jobs;
}

export function createJob({ name, objective, interval_sec, enabled = true }) {
  const nextName = normalizeText(name, 120);
  const nextObjective = normalizeText(objective, 5000);
  const nextInterval = normalizeInterval(interval_sec);
  if (!nextName) throw new Error('name is required');
  if (!nextObjective) throw new Error('objective is required');
  if (!nextInterval) throw new Error('interval_sec must be a positive integer');

  const db = readDb();
  const now = nowIso();
  const job = {
    id: randomUUID(),
    name: nextName,
    objective: nextObjective,
    interval_sec: nextInterval,
    enabled: Boolean(enabled),
    conversation_id: randomUUID(),
    last_run_at: null,
    last_status: 'idle',
    last_error: '',
    created_at: now,
    updated_at: now,
  };
  db.jobs.push(job);
  writeDb(db);
  return job;
}

export function updateJob(id, patch = {}) {
  const sid = String(id || '').trim();
  if (!sid) throw new Error('id is required');
  const db = readDb();
  const idx = db.jobs.findIndex((job) => job.id === sid);
  if (idx < 0) throw new Error(`job not found: ${sid}`);
  const prev = db.jobs[idx];
  const next = { ...prev };

  if (Object.prototype.hasOwnProperty.call(patch, 'name')) {
    const name = normalizeText(patch.name, 120);
    if (!name) throw new Error('name cannot be empty');
    next.name = name;
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'objective')) {
    const objective = normalizeText(patch.objective, 5000);
    if (!objective) throw new Error('objective cannot be empty');
    next.objective = objective;
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'interval_sec')) {
    const interval = normalizeInterval(patch.interval_sec);
    if (!interval) throw new Error('interval_sec must be a positive integer');
    next.interval_sec = interval;
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'enabled')) {
    next.enabled = Boolean(patch.enabled);
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'last_run_at')) {
    next.last_run_at = patch.last_run_at ? String(patch.last_run_at) : null;
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'last_status')) {
    next.last_status = String(patch.last_status || 'idle');
  }
  if (Object.prototype.hasOwnProperty.call(patch, 'last_error')) {
    next.last_error = String(patch.last_error || '');
  }

  next.updated_at = nowIso();
  db.jobs[idx] = next;
  writeDb(db);
  return next;
}

export function removeJob(id) {
  const sid = String(id || '').trim();
  if (!sid) throw new Error('id is required');
  const db = readDb();
  const before = db.jobs.length;
  db.jobs = db.jobs.filter((job) => job.id !== sid);
  if (db.jobs.length === before) return false;
  writeDb(db);
  return true;
}

export function jobsFilePath() {
  ensureDir();
  return JOBS_FILE;
}

export function loadDaemonState() {
  ensureDir();
  if (!existsSync(DAEMON_STATE_FILE)) return null;
  try {
    const parsed = JSON.parse(readFileSync(DAEMON_STATE_FILE, 'utf-8'));
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveDaemonState(state) {
  ensureDir();
  writeFileSync(DAEMON_STATE_FILE, JSON.stringify(state || {}, null, 2), 'utf-8');
}

export function clearDaemonState() {
  ensureDir();
  writeFileSync(DAEMON_STATE_FILE, JSON.stringify({}, null, 2), 'utf-8');
}
