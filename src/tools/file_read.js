import { readFileSync, statSync } from 'fs';
import { extname } from 'path';
import { tool } from './registry.js';

tool('file_read', 'Read a file. Supports text files with optional line range, and returns file info. Use this before file_write to understand file content.', {
  properties: {
    path: { type: 'string', description: 'File path to read' },
    start_line: { type: 'number', description: 'Start line number (1-based, optional)' },
    end_line: { type: 'number', description: 'End line number (inclusive, optional)' },
  },
  required: ['path'],
}, false, ({ path, start_line, end_line }) => {
  try {
    const stat = statSync(path);
    const size = stat.size;
    if (size > 5 * 1024 * 1024) return `[error] File too large (${(size/1024/1024).toFixed(1)}MB). Use shell_exec with head/tail.`;
    const bin = ['.png','.jpg','.gif','.zip','.exe','.dll','.bin','.pdf','.mp3','.mp4'];
    if (bin.includes(extname(path).toLowerCase())) return `[binary file] ${path} (${(size/1024).toFixed(1)}KB)`;
    const content = readFileSync(path, 'utf-8');
    if (start_line || end_line) {
      const lines = content.split('\n');
      const s = (start_line || 1) - 1;
      const e = end_line || lines.length;
      return lines.slice(s, e).map((l, i) => `${s + i + 1}| ${l}`).join('\n');
    }
    const lines = content.split('\n');
    if (lines.length > 500) {
      return `[${lines.length} lines, showing first 500]\n` + lines.slice(0, 500).map((l, i) => `${i+1}| ${l}`).join('\n');
    }
    return content;
  } catch (e) {
    return `[error] ${e.message}`;
  }
});
