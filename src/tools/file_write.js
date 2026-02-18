import { writeFileSync, readFileSync, mkdirSync, existsSync } from 'fs';
import { dirname } from 'path';
import { tool } from './registry.js';

tool('file_write', 'Write or patch a file. mode="write" overwrites entire file. mode="patch" replaces old_string with new_string (for surgical edits without rewriting the whole file).', {
  properties: {
    path: { type: 'string', description: 'File path' },
    content: { type: 'string', description: 'Full content (for write mode)' },
    mode: { type: 'string', description: '"write" (default) or "patch"' },
    old_string: { type: 'string', description: 'String to find (patch mode)' },
    new_string: { type: 'string', description: 'Replacement string (patch mode)' },
  },
  required: ['path'],
}, true, ({ path, content, mode = 'write', old_string, new_string }) => {
  try {
    mkdirSync(dirname(path) || '.', { recursive: true });
    if (mode === 'patch') {
      if (!existsSync(path)) return `[error] File not found: ${path}`;
      const src = readFileSync(path, 'utf-8');
      if (!src.includes(old_string)) return `[error] old_string not found in file`;
      const patched = src.replace(old_string, new_string);
      writeFileSync(path, patched, 'utf-8');
      return `Patched ${path}`;
    }
    writeFileSync(path, content, 'utf-8');
    return `Written ${content.length} chars to ${path}`;
  } catch (e) {
    return `[error] ${e.message}`;
  }
});
