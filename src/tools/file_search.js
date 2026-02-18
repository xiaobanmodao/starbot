import { glob } from 'glob';
import { readFileSync, statSync, readdirSync } from 'fs';
import { join, relative } from 'path';
import { tool } from './registry.js';

tool('file_search', 'Search files by glob pattern and/or content. Also supports listing directory tree.', {
  properties: {
    pattern: { type: 'string', description: "Glob pattern (e.g. '**/*.js') or directory path for tree listing" },
    grep: { type: 'string', description: 'Text or regex to search inside files (optional)' },
    max_results: { type: 'number', description: 'Max results (default 50)' },
  },
  required: ['pattern'],
}, false, async ({ pattern, grep = '', max_results = 50 }) => {
  try {
    // Directory tree mode
    try {
      const s = statSync(pattern);
      if (s.isDirectory()) return dirTree(pattern, '', 3);
    } catch {}

    const files = (await glob(pattern, { nodir: true })).slice(0, 200);
    if (!grep) return files.slice(0, max_results).join('\n') || 'No files found';

    const re = new RegExp(grep, 'i');
    const results = [];
    for (const f of files) {
      try {
        const lines = readFileSync(f, 'utf-8').split('\n');
        lines.forEach((line, i) => {
          if (re.test(line)) results.push(`${f}:${i + 1}: ${line.trim()}`);
        });
      } catch {}
      if (results.length >= max_results) break;
    }
    return results.slice(0, max_results).join('\n') || 'No matches found';
  } catch (e) {
    return `[error] ${e.message}`;
  }
});

function dirTree(dir, prefix, depth) {
  if (depth <= 0) return prefix + '...\n';
  let out = '';
  try {
    const entries = readdirSync(dir, { withFileTypes: true })
      .filter(e => !e.name.startsWith('.') && e.name !== 'node_modules')
      .slice(0, 50);
    entries.forEach((e, i) => {
      const last = i === entries.length - 1;
      const connector = last ? '└── ' : '├── ';
      const child = last ? '    ' : '│   ';
      out += prefix + connector + e.name + (e.isDirectory() ? '/' : '') + '\n';
      if (e.isDirectory()) out += dirTree(join(dir, e.name), prefix + child, depth - 1);
    });
  } catch {}
  return out;
}
