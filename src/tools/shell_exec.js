import { spawn } from 'child_process';
import { platform } from 'os';
import { tool } from './registry.js';

tool('shell_exec', 'Execute a shell command with full system privileges. Use for: running programs, installing packages, git, file management, system admin, compiling, process management, networking, etc.', {
  properties: {
    command: { type: 'string', description: 'Shell command to execute' },
    cwd: { type: 'string', description: 'Working directory (optional)' },
    timeout: { type: 'number', description: 'Timeout in seconds (default 120)' },
    env: { type: 'object', description: 'Extra environment variables (optional)' },
  },
  required: ['command'],
}, true, ({ command, cwd, timeout = 120, env }) => {
  return new Promise((resolve) => {
    const isWin = platform() === 'win32';
    const proc = spawn(command, {
      shell: isWin ? 'cmd.exe' : '/bin/sh',
      cwd: cwd || process.cwd(),
      timeout: timeout * 1000,
      env: env ? { ...process.env, ...env } : process.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '', stderr = '';
    proc.stdout.on('data', d => { stdout += d; });
    proc.stderr.on('data', d => { stderr += d; });
    proc.on('close', code => {
      let r = stdout;
      if (stderr) r += `\n[stderr]\n${stderr}`;
      if (code !== 0 && code != null) r += `\n[exit code: ${code}]`;
      resolve(r.slice(0, 50000) || '(no output)');
    });
    proc.on('error', e => resolve(`[error] ${e.message}`));
  });
});
