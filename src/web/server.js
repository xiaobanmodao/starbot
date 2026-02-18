import { createServer } from 'http';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { randomUUID } from 'crypto';
import { platform } from 'os';
import { spawn } from 'child_process';
import { Agent } from '../agent.js';
import { Client } from '../client.js';
import { saveConfig } from '../config.js';
import { getThemeNames } from '../render.js';
import { loadBuiltInTools, loadCustomTools } from '../tools/bootstrap.js';
import {
  clearConversation,
  deleteConversation,
  listConversations,
  loadConversation,
  renameConversation,
  saveConversation,
} from '../history/store.js';
import { collectConversationSummary, markSummaryReported } from '../automation/chat/reporting.js';

const WEB_DIR = join(process.cwd(), 'src', 'web');
const sessions = new Map();

function getOrCreateSession(sessionId, cfg) {
  if (sessions.has(sessionId)) return sessions.get(sessionId);
  const agent = new Agent(cfg);
  const record = loadConversation(sessionId);
  if (record?.messages?.length) agent.loadMessages(record.messages, true);
  const session = { agent };
  sessions.set(sessionId, session);
  return session;
}

function parseJsonBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => { data += chunk; });
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch (e) {
        reject(e);
      }
    });
    req.on('error', reject);
  });
}

function writeJson(res, code, body) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(body));
}

function writeSse(res, event, data) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

function openBrowser(url) {
  const os = platform();
  if (os === 'win32') {
    spawn('cmd', ['/c', 'start', '', url], { detached: true, stdio: 'ignore' }).unref();
    return;
  }
  if (os === 'darwin') {
    spawn('open', [url], { detached: true, stdio: 'ignore' }).unref();
    return;
  }
  spawn('xdg-open', [url], { detached: true, stdio: 'ignore' }).unref();
}

export async function runWeb(cfg, options = {}) {
  await loadBuiltInTools();
  await loadCustomTools();

  const host = options.host || '127.0.0.1';
  const port = options.port || 8787;
  const autoOpen = options.autoOpen !== false;

  const server = createServer(async (req, res) => {
    const url = req.url || '/';

    if (req.method === 'GET' && (url === '/' || url === '/index.html')) {
      const html = readFileSync(join(WEB_DIR, 'index.html'), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
      return;
    }
    if (req.method === 'GET' && url === '/app.js') {
      const js = readFileSync(join(WEB_DIR, 'app.js'), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'application/javascript; charset=utf-8' });
      res.end(js);
      return;
    }
    if (req.method === 'GET' && url === '/styles.css') {
      const css = readFileSync(join(WEB_DIR, 'styles.css'), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'text/css; charset=utf-8' });
      res.end(css);
      return;
    }
    if (req.method === 'GET' && url === '/favicon.ico') {
      if (existsSync(join(WEB_DIR, 'favicon.ico'))) {
        res.writeHead(200, { 'Content-Type': 'image/x-icon' });
        res.end(readFileSync(join(WEB_DIR, 'favicon.ico')));
      } else {
        res.writeHead(204);
        res.end();
      }
      return;
    }

    if (req.method === 'GET' && url === '/api/state') {
      writeJson(res, 200, {
        model: cfg.model,
        color_theme: cfg.color_theme || 'ocean',
        themes: getThemeNames(),
      });
      return;
    }
    if (req.method === 'GET' && url === '/api/models') {
      try {
        const client = new Client(cfg);
        const models = await client.listModels();
        writeJson(res, 200, { models });
      } catch (e) {
        writeJson(res, 500, { error: e.message });
      }
      return;
    }
    if (req.method === 'GET' && url === '/api/history') {
      writeJson(res, 200, { items: listConversations() });
      return;
    }
    if (req.method === 'GET' && url.startsWith('/api/history-item')) {
      const parsed = new URL(url, 'http://localhost');
      const id = String(parsed.searchParams.get('id') || '');
      const activate = parsed.searchParams.get('activate') === '1';
      const item = loadConversation(id);
      if (!item) {
        writeJson(res, 404, { error: 'not found' });
        return;
      }
      if (activate) {
        sessions.delete(id);
        getOrCreateSession(id, cfg);
      }
      writeJson(res, 200, item);
      return;
    }
    if (req.method === 'POST' && url === '/api/history-rename') {
      try {
        const body = await parseJsonBody(req);
        const id = String(body.id || '');
        const title = String(body.title || '');
        const updated = renameConversation(id, title);
        if (!updated) return writeJson(res, 400, { error: 'rename failed' });
        writeJson(res, 200, { ok: true, item: updated });
      } catch (e) {
        writeJson(res, 500, { error: e.message });
      }
      return;
    }
    if (req.method === 'POST' && url === '/api/history-delete') {
      try {
        const body = await parseJsonBody(req);
        const id = String(body.id || '');
        const ok = deleteConversation(id);
        sessions.delete(id);
        if (!ok) return writeJson(res, 400, { error: 'delete failed' });
        writeJson(res, 200, { ok: true });
      } catch (e) {
        writeJson(res, 500, { error: e.message });
      }
      return;
    }

    if (req.method === 'POST' && url === '/api/set-model') {
      try {
        const body = await parseJsonBody(req);
        const model = String(body.model || '').trim();
        if (!model) return writeJson(res, 400, { error: 'model is required' });
        cfg.model = model;
        saveConfig(cfg);
        sessions.clear();
        writeJson(res, 200, { ok: true, model });
      } catch (e) {
        writeJson(res, 500, { error: e.message });
      }
      return;
    }
    if (req.method === 'POST' && url === '/api/set-theme') {
      try {
        const body = await parseJsonBody(req);
        const theme = String(body.theme || '').trim().toLowerCase();
        const themes = getThemeNames();
        if (!themes.includes(theme)) return writeJson(res, 400, { error: 'invalid theme' });
        cfg.color_theme = theme;
        saveConfig(cfg);
        writeJson(res, 200, { ok: true, color_theme: theme });
      } catch (e) {
        writeJson(res, 500, { error: e.message });
      }
      return;
    }

    if (req.method === 'POST' && url === '/api/chat/stream') {
      try {
        const body = await parseJsonBody(req);
        const sessionId = String(body.sessionId || randomUUID());
        const message = String(body.message || '').trim();
        if (!message) return writeJson(res, 400, { error: 'message is required' });

        const { agent } = getOrCreateSession(sessionId, cfg);
        agent.setOriginConversationId(sessionId);
        res.writeHead(200, {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'Cache-Control': 'no-cache, no-transform',
          Connection: 'keep-alive',
        });
        writeSse(res, 'session', { sessionId });

                const summary = collectConversationSummary(sessionId);
        if (summary) {
          writeSse(res, 'answer_start', {});
          writeSse(res, 'answer', { chunk: `${summary.text}\n\n` });
          markSummaryReported(summary.resultIds);
        }

        let sawTool = false;
        let hadToolResult = false;
        let answerStarted = false;
        let usage = null;

        for await (const ev of agent.run(message)) {
          if (ev.type === 'usage') {
            usage = ev.cumulative;
            continue;
          }
          if (ev.type === 'tool_call') {
            sawTool = true;
            continue;
          }
          if (ev.type === 'tool_result') {
            hadToolResult = true;
            continue;
          }
          if (ev.type === 'text') {
            const chunk = String(ev.content || '');
            const isAnswer = !sawTool || hadToolResult;
            if (isAnswer) {
              if (!answerStarted) {
                answerStarted = true;
                writeSse(res, 'answer_start', {});
              }
              writeSse(res, 'answer', { chunk });
            } else {
              writeSse(res, 'thinking', { chunk });
            }
            continue;
          }
          if (ev.type === 'error') writeSse(res, 'error', { message: ev.message || 'unknown error' });
        }

        if (usage) writeSse(res, 'usage', usage);
        saveConversation({ id: sessionId, messages: agent.getMessages() });
        writeSse(res, 'done', {});
        res.end();
      } catch (e) {
        writeJson(res, 500, { error: e.message });
      }
      return;
    }

    if (req.method === 'POST' && url === '/api/clear') {
      try {
        const body = await parseJsonBody(req);
        const sessionId = String(body.sessionId || '');
        if (sessionId && sessions.has(sessionId)) sessions.get(sessionId).agent.reset();
        if (sessionId) clearConversation(sessionId);
        writeJson(res, 200, { ok: true });
      } catch (e) {
        writeJson(res, 500, { error: e.message });
      }
      return;
    }

    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not found');
  });

  await new Promise((resolve) => server.listen(port, host, resolve));
  const url = `http://${host}:${port}`;
  console.log(`Web UI running at ${url}`);
  if (autoOpen) openBrowser(url);
}

