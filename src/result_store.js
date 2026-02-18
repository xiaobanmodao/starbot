import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import { randomUUID } from 'crypto';

const STARBOT_DIR = join(homedir(), '.starbot');
const RESULTS_FILE = join(STARBOT_DIR, 'daemon_results.json');

function ensureDir() {
  mkdirSync(STARBOT_DIR, { recursive: true });
}

function nowIso() {
  return new Date().toISOString();
}

function readDb() {
  ensureDir();
  if (!existsSync(RESULTS_FILE)) return { results: [] };
  try {
    const parsed = JSON.parse(readFileSync(RESULTS_FILE, 'utf-8'));
    return { results: Array.isArray(parsed?.results) ? parsed.results : [] };
  } catch {
    return { results: [] };
  }
}

function writeDb(db) {
  ensureDir();
  const safe = { results: Array.isArray(db?.results) ? db.results : [] };
  writeFileSync(RESULTS_FILE, JSON.stringify(safe, null, 2), 'utf-8');
}

export function addResult({ origin_conversation_id, job_id, summary, payload, status = 'completed' }) {
  const origin = String(origin_conversation_id || '').trim();
  if (!origin) throw new Error('origin_conversation_id is required');
  const db = readDb();
  const now = nowIso();
  const item = {
    id: randomUUID(),
    origin_conversation_id: origin,
    job_id: String(job_id || ''),
    summary: String(summary || '').trim(),
    payload: payload ?? null,
    status: String(status || 'completed'),
    reported: false,
    created_at: now,
    reported_at: null,
  };
  db.results.push(item);
  writeDb(db);
  return item;
}

export function listPendingResults(originConversationId) {
  const origin = String(originConversationId || '').trim();
  if (!origin) return [];
  return readDb().results.filter((item) => !item.reported && item.origin_conversation_id === origin);
}

export function markResultsReported(ids = []) {
  const sid = new Set((Array.isArray(ids) ? ids : []).map((id) => String(id)));
  if (!sid.size) return 0;
  const db = readDb();
  let changed = 0;
  const now = nowIso();
  for (const item of db.results) {
    if (sid.has(String(item.id)) && !item.reported) {
      item.reported = true;
      item.reported_at = now;
      changed += 1;
    }
  }
  if (changed) writeDb(db);
  return changed;
}

export function resultsFilePath() {
  ensureDir();
  return RESULTS_FILE;
}
