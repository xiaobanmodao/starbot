import { unlinkSync } from 'fs';

export function deleteFileAction(input = {}) {
  const path = String(input.path || '').trim();
  try {
    unlinkSync(path);
    return {
      action: 'delete_file',
      path,
      success: true,
      error: null,
      timestamp: new Date().toISOString(),
    };
  } catch (e) {
    return {
      action: 'delete_file',
      path,
      success: false,
      error: String(e?.message || e || 'unknown error'),
      timestamp: new Date().toISOString(),
    };
  }
}
