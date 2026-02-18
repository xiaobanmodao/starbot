import { spawn } from 'child_process';
import { writeFileSync, unlinkSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { platform } from 'os';
import { tool } from './registry.js';

tool('python_exec', 'Execute Python code. Writes to temp file so multiline code, imports, and complex scripts all work. Use for data processing, calculations, automation, etc.', {
  properties: {
    code: { type: 'string', description: 'Python code to execute' },
    timeout: { type: 'number', description: 'Timeout in seconds (default 60)' },
  },
  required: ['code'],
}, true, ({ code, timeout = 60 }) => {
  const tmp = join(tmpdir(), `starbot_${Date.now()}.py`);
  writeFileSync(tmp, code, 'utf-8');
  const cmd = platform() === 'win32' ? 'python' : 'python3';
  return new Promise(resolve => {
    const proc = spawn(cmd, [tmp], {
      timeout: timeout * 1000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '', stderr = '';
    proc.stdout.on('data', d => { stdout += d; });
    proc.stderr.on('data', d => { stderr += d; });
    proc.on('close', code => {
      try { unlinkSync(tmp); } catch {}
      let r = stdout;
      if (stderr) r += `\n[stderr]\n${stderr}`;
      if (code !== 0 && code != null) r += `\n[exit code: ${code}]`;
      resolve(r.slice(0, 50000) || '(no output)');
    });
    proc.on('error', e => {
      try { unlinkSync(tmp); } catch {}
      resolve(`[error] ${e.message}`);
    });
  });
});
