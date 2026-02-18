import { spawn } from 'child_process';
import { platform } from 'os';
import { tool } from './registry.js';

function runShell(command, timeout = 30) {
  return new Promise((resolve) => {
    const shell = platform() === 'win32' ? 'cmd.exe' : '/bin/sh';
    const args = platform() === 'win32' ? ['/c', command] : ['-c', command];
    const proc = spawn(shell, args, { timeout: timeout * 1000, stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (d) => { stdout += d; });
    proc.stderr.on('data', (d) => { stderr += d; });
    proc.on('close', (code) => {
      let out = stdout;
      if (stderr) out += `\n[stderr]\n${stderr}`;
      if (code !== 0 && code != null) out += `\n[exit code: ${code}]`;
      resolve(out.trim() || '(no output)');
    });
    proc.on('error', (e) => resolve(`[error] ${e.message}`));
  });
}

tool('process_manage', 'Manage local processes: list top processes, start new process, or kill existing process by pid/name.', {
  properties: {
    action: { type: 'string', description: 'list | start | kill' },
    command: { type: 'string', description: 'Command to start when action=start' },
    pid: { type: 'number', description: 'Process id for action=kill' },
    name: { type: 'string', description: 'Process name for action=kill' },
    timeout: { type: 'number', description: 'Timeout in seconds for shell operations' },
  },
  required: ['action'],
}, true, async ({ action, command, pid, name, timeout = 30 }) => {
  const mode = String(action || '').toLowerCase();
  if (mode === 'list') {
    return platform() === 'win32'
      ? runShell('tasklist', timeout)
      : runShell('ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 80', timeout);
  }

  if (mode === 'start') {
    if (!command) return '[error] action=start requires command';
    try {
      const isWin = platform() === 'win32';
      const proc = spawn(command, {
        shell: isWin ? 'cmd.exe' : '/bin/sh',
        detached: true,
        stdio: 'ignore',
      });
      proc.unref();
      return `Started process PID=${proc.pid}`;
    } catch (e) {
      return `[error] ${e.message}`;
    }
  }

  if (mode === 'kill') {
    if (pid) {
      try {
        process.kill(Number(pid), 'SIGTERM');
        return `Sent SIGTERM to PID=${pid}`;
      } catch (e) {
        return `[error] ${e.message}`;
      }
    }
    if (name) {
      return platform() === 'win32'
        ? runShell(`taskkill /IM "${name}" /F`, timeout)
        : runShell(`pkill -f "${name.replace(/"/g, '\\"')}"`, timeout);
    }
    return '[error] action=kill requires pid or name';
  }

  return '[error] Unknown action, use list/start/kill';
});
