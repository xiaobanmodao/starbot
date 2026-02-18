import { watchFileExists } from './file_exists.js';

export function runWatcher(spec = {}) {
  const type = String(spec?.type || '').trim();
  if (type === 'file_exists') return watchFileExists(spec);
  return {
    matched: false,
    type: type || 'unknown',
    target: '',
    timestamp: new Date().toISOString(),
  };
}
