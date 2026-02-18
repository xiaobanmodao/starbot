import { deleteFileAction } from './delete_file.js';

export function runAction(spec = {}) {
  const type = String(spec?.type || '').trim();
  if (type === 'delete_file') return deleteFileAction(spec);
  return {
    action: type || 'unknown',
    path: String(spec?.path || ''),
    success: false,
    error: `unsupported action: ${type || 'unknown'}`,
    timestamp: new Date().toISOString(),
  };
}
