import { randomUUID } from 'crypto';
import { filePath, nowIso, readJson, writeJson } from './base.js';

const FILE = 'automation_results.json';

function readDb() {
  const parsed = readJson(FILE, { results: [] });
  const results = Array.isArray(parsed?.results) ? parsed.results : [];
  return { results };
}

function writeDb(db) {
  writeJson(FILE, { results: Array.isArray(db?.results) ? db.results : [] });
}

export function addResult({
  task_id,
  origin_conversation_id,
  event,
  status = 'ok',
  details = null,
}) {
  const task = String(task_id || '').trim();
  const origin = String(origin_conversation_id || '').trim();
  const evt = String(event || '').trim();
  if (!task) throw new Error('task_id is required');
  if (!origin) throw new Error('origin_conversation_id is required');
  if (!evt) throw new Error('event is required');
  const db = readDb();
  db.results.push({
    id: randomUUID(),
    task_id: task,
    origin_conversation_id: origin,
    event: evt,
    timestamp: nowIso(),
    status: String(status || 'ok'),
    details,
    reported: false,
    reported_at: null,
  });
  writeDb(db);
}

export function listPendingByConversation(originConversationId) {
  const sid = String(originConversationId || '').trim();
  if (!sid) return [];
  return readDb().results.filter((item) => !item.reported && item.origin_conversation_id === sid);
}

export function markReported(ids = []) {
  const set = new Set((Array.isArray(ids) ? ids : []).map((id) => String(id)));
  if (!set.size) return 0;
  const db = readDb();
  const now = nowIso();
  let changed = 0;
  for (const item of db.results) {
    if (set.has(String(item.id)) && !item.reported) {
      item.reported = true;
      item.reported_at = now;
      changed += 1;
    }
  }
  if (changed) writeDb(db);
  return changed;
}

export function resultsFilePath() {
  return filePath(FILE);
}
