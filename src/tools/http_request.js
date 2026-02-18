import { tool } from './registry.js';

tool('http_request', 'Make HTTP requests. Supports all methods, custom headers, body, and returns status + response body.', {
  properties: {
    method: { type: 'string', description: 'HTTP method (GET/POST/PUT/DELETE/PATCH)' },
    url: { type: 'string', description: 'Request URL' },
    headers: { type: 'object', description: 'Request headers (optional)' },
    body: { type: 'string', description: 'Request body (optional)' },
    timeout: { type: 'number', description: 'Timeout in seconds (default 30)' },
  },
  required: ['method', 'url'],
}, false, async ({ method, url, headers = {}, body = null, timeout = 30 }) => {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout * 1000);
    const opts = { method: method.toUpperCase(), headers, redirect: 'follow', signal: ctrl.signal };
    if (body) {
      opts.body = body;
      opts.headers['Content-Type'] = opts.headers['Content-Type'] || 'application/json';
    }
    const r = await fetch(url, opts);
    clearTimeout(timer);
    const respHeaders = Object.fromEntries(r.headers.entries());
    const text = (await r.text()).slice(0, 20000);
    return `[${r.status} ${r.statusText}]\n[headers] ${JSON.stringify(respHeaders)}\n\n${text}`;
  } catch (e) {
    return `[error] ${e.message}`;
  }
});
