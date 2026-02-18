import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, unlinkSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const HISTORY_DIR = join(homedir(), '.starbot', 'history');

function ensureDir() {
  mkdirSync(HISTORY_DIR, { recursive: true });
}

function safeId(id) {
  return String(id || '').replace(/[^a-zA-Z0-9_-]/g, '');
}

function filePath(id) {
  return join(HISTORY_DIR, `${safeId(id)}.json`);
}

function textFromMessage(msg) {
  if (!msg) return '';
  if (typeof msg.content === 'string') return msg.content;
  return '';
}

function buildTitle(messages = []) {
  const firstUser = messages.find((message) => message?.role === 'user');
  const raw = (textFromMessage(firstUser) || 'New Conversation').replace(/\s+/g, ' ').trim();
  return raw.slice(0, 64) || 'New Conversation';
}

export function saveConversation(record) {
  ensureDir();
  const id = safeId(record?.id);
  if (!id) throw new Error('Invalid conversation id');
  const messages = Array.isArray(record?.messages) ? record.messages : [];
  const now = new Date().toISOString();
  const payload = {
    id,
    title: String(record?.title || buildTitle(messages)),
    createdAt: record?.createdAt || now,
    updatedAt: now,
    messages,
  };
  writeFileSync(filePath(id), JSON.stringify(payload, null, 2), 'utf-8');
  return payload;
}

export function loadConversation(id) {
  const sid = safeId(id);
  if (!sid) return null;
  const full = filePath(sid);
  if (!existsSync(full)) return null;
  try {
    const parsed = JSON.parse(readFileSync(full, 'utf-8'));
    if (!Array.isArray(parsed.messages)) parsed.messages = [];
    return parsed;
  } catch {
    return null;
  }
}

export function listConversations(limit = 200) {
  ensureDir();
  const files = readdirSync(HISTORY_DIR)
    .filter((name) => name.endsWith('.json'))
    .slice(0, limit);
  const items = [];
  for (const name of files) {
    try {
      const parsed = JSON.parse(readFileSync(join(HISTORY_DIR, name), 'utf-8'));
      items.push({
        id: parsed.id,
        title: parsed.title || 'Untitled',
        updatedAt: parsed.updatedAt || parsed.createdAt || '',
      });
    } catch {}
  }
  return items.sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
}

export function clearConversation(id) {
  const loaded = loadConversation(id);
  if (!loaded) return null;
  return saveConversation({
    ...loaded,
    messages: (loaded.messages || []).filter((message) => message.role === 'system'),
  });
}

export function renameConversation(id, title) {
  const loaded = loadConversation(id);
  if (!loaded) return null;
  const nextTitle = String(title || '').trim().slice(0, 80);
  if (!nextTitle) return null;
  return saveConversation({
    ...loaded,
    title: nextTitle,
    messages: loaded.messages || [],
  });
}

export function deleteConversation(id) {
  const sid = safeId(id);
  if (!sid) return false;
  const full = filePath(sid);
  if (!existsSync(full)) return false;
  try {
    unlinkSync(full);
    return true;
  } catch {
    return false;
  }
}

export function historyDir() {
  ensureDir();
  return HISTORY_DIR;
}
