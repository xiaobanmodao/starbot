import { filePath, nowIso, readJson, writeJson } from './base.js';

const FILE = 'automation_daemon_state.json';

export function loadDaemonState() {
  const parsed = readJson(FILE, {});
  return (parsed && typeof parsed === 'object') ? parsed : {};
}

export function saveDaemonState(state) {
  writeJson(FILE, state || {});
}

export function setDaemonRunning(pid) {
  saveDaemonState({
    status: 'running',
    pid: Number(pid) || null,
    started_at: nowIso(),
  });
}

export function clearDaemonState() {
  saveDaemonState({});
}

export function daemonStateFilePath() {
  return filePath(FILE);
}
