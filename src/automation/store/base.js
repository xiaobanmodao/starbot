import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const ROOT_DIR = join(homedir(), '.starbot');

function ensureRoot() {
  mkdirSync(ROOT_DIR, { recursive: true });
}

export function readJson(fileName, fallback) {
  ensureRoot();
  const full = join(ROOT_DIR, fileName);
  if (!existsSync(full)) return fallback;
  try {
    return JSON.parse(readFileSync(full, 'utf-8'));
  } catch {
    return fallback;
  }
}

export function writeJson(fileName, value) {
  ensureRoot();
  const full = join(ROOT_DIR, fileName);
  writeFileSync(full, JSON.stringify(value, null, 2), 'utf-8');
  return full;
}

export function filePath(fileName) {
  ensureRoot();
  return join(ROOT_DIR, fileName);
}

export function nowIso() {
  return new Date().toISOString();
}
