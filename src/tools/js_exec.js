import { tool } from './registry.js';

tool('js_exec', 'Execute JavaScript/Node.js code directly in the current process. Has full access to Node.js APIs (fs, path, os, child_process, etc). Faster than shell_exec for JS tasks. Use for: data processing, JSON manipulation, quick calculations, file operations via Node API, etc.', {
  properties: {
    code: { type: 'string', description: 'JavaScript code to execute. Use console.log() for output. Last expression value is also captured.' },
  },
  required: ['code'],
}, true, async ({ code }) => {
  const logs = [];
  const fakeConsole = { ...console, log: (...a) => logs.push(a.map(String).join(' ')), error: (...a) => logs.push('[err] ' + a.map(String).join(' ')) };
  try {
    const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
    const fn = new AsyncFunction('console', 'require', code);
    const { createRequire } = await import('module');
    const require = createRequire(import.meta.url);
    const result = await fn(fakeConsole, require);
    let out = logs.join('\n');
    if (result !== undefined) out += (out ? '\n' : '') + String(result);
    return out || '(no output)';
  } catch (e) {
    return logs.join('\n') + '\n[error] ' + e.message;
  }
});
