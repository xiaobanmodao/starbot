import { spawn } from 'child_process';

export function notifySystem(eventText) {
  const text = String(eventText || '').trim();
  if (!text) return false;
  if (process.platform !== 'win32') return false;
  const esc = text.replace(/'/g, "''");
  const script = `[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null; [System.Windows.Forms.MessageBox]::Show('${esc}','StarBot Automation') | Out-Null`;
  const child = spawn('powershell.exe', ['-NoProfile', '-Command', script], {
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
  return true;
}
