import { spawn } from 'child_process';
import { platform } from 'os';
import { tool } from './registry.js';

tool('powershell_exec', 'Execute PowerShell script on Windows. Supports multiline scripts and full system capabilities.', {
  properties: {
    script: { type: 'string', description: 'PowerShell script content' },
    cwd: { type: 'string', description: 'Working directory (optional)' },
    timeout: { type: 'number', description: 'Timeout in seconds (default 180)' },
  },
  required: ['script'],
}, true, ({ script, cwd, timeout = 180 }) => {
  return new Promise((resolve) => {
    if (platform() !== 'win32') {
      resolve('[error] powershell_exec is only available on Windows');
      return;
    }
    const proc = spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script], {
      cwd: cwd || process.cwd(),
      timeout: timeout * 1000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (d) => { stdout += d; });
    proc.stderr.on('data', (d) => { stderr += d; });
    proc.on('close', (code) => {
      let out = stdout;
      if (stderr) out += `\n[stderr]\n${stderr}`;
      if (code !== 0 && code != null) out += `\n[exit code: ${code}]`;
      resolve(out.slice(0, 50000) || '(no output)');
    });
    proc.on('error', (e) => resolve(`[error] ${e.message}`));
  });
});
