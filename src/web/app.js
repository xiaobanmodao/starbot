const chatEl = document.querySelector('#chat');
const inputEl = document.querySelector('#input');
const sendBtn = document.querySelector('#sendBtn');
const clearBtn = document.querySelector('#clearBtn');
const newChatBtn = document.querySelector('#newChatBtn');
const historyListEl = document.querySelector('#historyList');
const modelSelect = document.querySelector('#modelSelect');
const themeSelect = document.querySelector('#themeSelect');
const tpl = document.querySelector('#msgTpl');

let sessionId = localStorage.getItem('starbot_session_id') || '';
let pending = false;
let modelsLoaded = false;

function isSafeHttpUrl(raw) {
  try {
    const u = new URL(raw);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

function setMessageContent(contentEl, text) {
  const value = String(text || '');
  contentEl.innerHTML = '';
  const pattern = /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s]+?\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?[^\s]*)?)/gi;
  let last = 0;
  let match;
  while ((match = pattern.exec(value)) !== null) {
    if (match.index > last) contentEl.appendChild(document.createTextNode(value.slice(last, match.index)));
    const alt = match[1] || 'image';
    const url = match[2] || match[3];
    if (isSafeHttpUrl(url)) {
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      const img = document.createElement('img');
      img.src = url;
      img.alt = alt;
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      img.className = 'chat-image';
      a.appendChild(img);
      contentEl.appendChild(a);
    } else {
      contentEl.appendChild(document.createTextNode(match[0]));
    }
    last = pattern.lastIndex;
  }
  if (last < value.length) contentEl.appendChild(document.createTextNode(value.slice(last)));
}

function appendMessage(role, content, cls = '') {
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.classList.add(cls || role);
  node.querySelector('.role').textContent = role;
  setMessageContent(node.querySelector('.content'), content);
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
  return node;
}

function appendThinkingMessage() {
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.classList.add('thinking');
  node.setAttribute('data-loading-thinking', '1');
  node.querySelector('.role').textContent = 'thinking';
  node.querySelector('.content').innerHTML = `
    <div class="thinking-row">
      <div class="win-spinner" aria-label="loading"></div>
      <span class="thinking-text">思考中...</span>
    </div>
  `;
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
  return node;
}

function stopThinkingAnimation(node) {
  if (!node) return;
  node.removeAttribute('data-loading-thinking');
  const loader = node.querySelector('.win-spinner');
  if (loader) loader.remove();
}

function removeThinkingIfEmpty(node) {
  if (!node) return;
  const text = String(node.querySelector('.thinking-text')?.textContent || '').trim();
  if (!text || text === '思考中...' || text === '思考中') node.remove();
}

function updateThinkingText(node, chunk) {
  if (!node) return;
  const textEl = node.querySelector('.thinking-text');
  if (!textEl) return;
  const current = textEl.textContent || '';
  textEl.textContent = (current === '思考中...' ? '' : current) + String(chunk || '');
  chatEl.scrollTop = chatEl.scrollHeight;
}

function createAssistantMessage() {
  const node = appendMessage('starbot', '', 'assistant');
  return node.querySelector('.content');
}

function appendAssistantChunk(contentEl, chunk) {
  if (!contentEl) return;
  contentEl.textContent += String(chunk || '');
  chatEl.scrollTop = chatEl.scrollHeight;
}

function handleSseRecord(record, handlers) {
  const lines = record.split('\n').map((line) => line.trimEnd());
  let event = 'message';
  let dataText = '';
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    if (line.startsWith('data:')) dataText += line.slice(5).trim();
  }
  if (!dataText) return;
  let data = null;
  try {
    data = JSON.parse(dataText);
  } catch {
    return;
  }
  if (handlers[event]) handlers[event](data);
}

async function send() {
  const message = inputEl.value.trim();
  if (!message || pending) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';
  appendMessage('you', message, 'user');
  pending = true;
  sendBtn.disabled = true;

  const thinkingNode = appendThinkingMessage();
  let assistantContentEl = null;
  let gotAnswerToken = false;
  let usage = null;

  try {
    const res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, message }),
    });
    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || 'request failed');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    const handlers = {
      session(data) {
        if (!data?.sessionId) return;
        sessionId = data.sessionId;
        localStorage.setItem('starbot_session_id', sessionId);
      },
      thinking(data) {
        updateThinkingText(thinkingNode, data?.chunk || '');
      },
      answer_start() {
        stopThinkingAnimation(thinkingNode);
        removeThinkingIfEmpty(thinkingNode);
        if (!assistantContentEl) assistantContentEl = createAssistantMessage();
      },
      answer(data) {
        if (!gotAnswerToken) {
          gotAnswerToken = true;
          stopThinkingAnimation(thinkingNode);
          removeThinkingIfEmpty(thinkingNode);
          if (!assistantContentEl) assistantContentEl = createAssistantMessage();
        }
        appendAssistantChunk(assistantContentEl, data?.chunk || '');
      },
      usage(data) { usage = data; },
      error(data) { appendMessage('error', data?.message || 'error'); },
      done() {},
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep = buffer.indexOf('\n\n');
      while (sep >= 0) {
        const record = buffer.slice(0, sep).trim();
        buffer = buffer.slice(sep + 2);
        if (record) handleSseRecord(record, handlers);
        sep = buffer.indexOf('\n\n');
      }
    }

    if (!gotAnswerToken) {
      stopThinkingAnimation(thinkingNode);
      removeThinkingIfEmpty(thinkingNode);
      if (!assistantContentEl) assistantContentEl = createAssistantMessage();
    }
    if (assistantContentEl) {
      setMessageContent(assistantContentEl, assistantContentEl.textContent || '');
    }
    // Web UI keeps output minimal: do not show token usage.
    await loadHistory();
  } catch (e) {
    stopThinkingAnimation(thinkingNode);
    removeThinkingIfEmpty(thinkingNode);
    appendMessage('error', e.message || String(e));
  } finally {
    pending = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

function renderConversation(messages = []) {
  chatEl.innerHTML = '';
  for (const msg of messages) {
    if (!msg || msg.role === 'system' || msg.role === 'tool') continue;
    if (msg.role === 'user') appendMessage('you', msg.content || '', 'user');
    else appendMessage('starbot', msg.content || '', 'assistant');
  }
  if (!chatEl.children.length) appendMessage('system', '新会话，输入任务开始。');
}

async function renameHistory(id) {
  const item = Array.from(historyListEl.querySelectorAll('.history-item'))
    .map((el) => ({ id: el.dataset.id, title: el.querySelector('.title')?.textContent || '' }))
    .find((entry) => entry.id === id);
  const current = item?.title || '';
  const next = prompt('新的会话名称：', current);
  if (next == null) return;
  const title = String(next).trim();
  if (!title) return;
  try {
    const res = await fetch('/api/history-rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, title }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'rename failed');
    await loadHistory();
  } catch (e) {
    appendMessage('error', e.message || String(e));
  }
}

async function deleteHistory(id) {
  if (!confirm('确认删除这条历史对话吗？')) return;
  try {
    const res = await fetch('/api/history-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'delete failed');
    if (id === sessionId) {
      newConversation();
      return;
    }
    await loadHistory();
  } catch (e) {
    appendMessage('error', e.message || String(e));
  }
}

async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    historyListEl.innerHTML = '';
    for (const item of items) {
      const el = document.createElement('div');
      el.className = `history-item${item.id === sessionId ? ' active' : ''}`;
      el.dataset.id = item.id;
      const time = item.updatedAt ? new Date(item.updatedAt).toLocaleString() : '';
      el.innerHTML = `
        <div class="history-row">
          <div class="title">${item.title || 'Untitled'}</div>
          <div class="history-actions">
            <button class="icon-btn rename" title="重命名">✎</button>
            <button class="icon-btn delete" title="删除">✕</button>
          </div>
        </div>
        <div class="time">${time}</div>
      `;
      el.addEventListener('click', () => openHistory(item.id));
      el.querySelector('.rename')?.addEventListener('click', (event) => {
        event.stopPropagation();
        renameHistory(item.id);
      });
      el.querySelector('.delete')?.addEventListener('click', (event) => {
        event.stopPropagation();
        deleteHistory(item.id);
      });
      historyListEl.appendChild(el);
    }
  } catch (e) {
    historyListEl.innerHTML = `<div class="history-item"><div class="title">Load failed</div><div class="time">${String(e.message || e)}</div></div>`;
  }
}

async function openHistory(id) {
  try {
    const res = await fetch(`/api/history-item?id=${encodeURIComponent(id)}&activate=1`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'load failed');
    sessionId = data.id;
    localStorage.setItem('starbot_session_id', sessionId);
    renderConversation(data.messages || []);
    await loadHistory();
  } catch (e) {
    appendMessage('error', e.message || String(e));
  }
}

function newConversation() {
  sessionId = crypto.randomUUID();
  localStorage.setItem('starbot_session_id', sessionId);
  chatEl.innerHTML = '';
  appendMessage('system', '新会话已创建。');
  loadHistory();
}

async function initControls() {
  try {
    const stateRes = await fetch('/api/state');
    const state = await stateRes.json();
    const themes = Array.isArray(state.themes) ? state.themes : [];
    themeSelect.innerHTML = themes.map((name) => `<option value="${name}">${name}</option>`).join('');
    if (state.color_theme) {
      themeSelect.value = state.color_theme;
      document.body.dataset.theme = state.color_theme;
    }
  } catch {}
  loadModels();
}

async function loadModels() {
  if (modelsLoaded) return;
  modelsLoaded = true;
  modelSelect.innerHTML = '<option value="">loading...</option>';
  try {
    const stateRes = await fetch('/api/state');
    const state = await stateRes.json();
    const modelRes = await fetch('/api/models');
    const modelData = await modelRes.json();
    const models = Array.isArray(modelData.models) ? modelData.models : [];
    modelSelect.innerHTML = models.map((name) => `<option value="${name}">${name}</option>`).join('');
    if (state.model) modelSelect.value = state.model;
  } catch {
    modelSelect.innerHTML = '<option value="">load failed</option>';
  }
}

sendBtn.addEventListener('click', send);
clearBtn.addEventListener('click', async () => {
  if (!sessionId) return;
  await fetch('/api/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId }),
  });
  chatEl.innerHTML = '';
  appendMessage('system', '会话已清空。');
  loadHistory();
});
newChatBtn.addEventListener('click', newConversation);

modelSelect.addEventListener('change', async () => {
  const model = modelSelect.value;
  if (!model) return;
  try {
    const res = await fetch('/api/set-model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'set model failed');
    appendMessage('system', `模型已切换为 ${model}`);
  } catch (e) {
    appendMessage('error', e.message || String(e));
  }
});

themeSelect.addEventListener('change', async () => {
  const theme = themeSelect.value;
  if (!theme) return;
  document.body.dataset.theme = theme;
  try {
    const res = await fetch('/api/set-theme', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'set theme failed');
  } catch (e) {
    appendMessage('error', e.message || String(e));
  }
});

inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 180)}px`;
});

appendMessage('system', 'Web mode ready. 输入任务开始。');
initControls();
loadHistory();
