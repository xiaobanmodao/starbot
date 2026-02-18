import { existsSync } from 'fs';

export function watchFileExists(input = {}) {
  const path = String(input.path || '').trim();
  const matched = Boolean(path) && existsSync(path);
  return {
    matched,
    type: 'file_exists',
    target: path,
    timestamp: new Date().toISOString(),
  };
}
