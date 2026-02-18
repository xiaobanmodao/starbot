import readline from 'readline/promises';
import * as readlineCore from 'readline';
import { randomUUID } from 'crypto';
import { Agent } from './agent.js';
import { saveConfig } from './config.js';
import { Client } from './client.js';
import * as render from './render.js';
import { loadBuiltInTools, loadCustomTools } from './tools/bootstrap.js';
import { getAllTools } from './tools/registry.js';
import {
  deleteConversation,
  historyDir,
  listConversations,
  loadConversation,
  renameConversation,
  saveConversation,
  clearConversation,
} from './history/store.js';
import { listPendingResults, markResultsReported } from './result_store.js';

const COMMAND_HINTS = [
  { cmd: '/help', desc: 'show commands' },
  { cmd: '/new', desc: 'new conversation' },
  { cmd: '/name', desc: 'rename conversation' },
  { cmd: '/delete', desc: 'delete conversation' },
  { cmd: '/tools', desc: 'browse tools' },
  { cmd: '/model', desc: 'select model' },
  { cmd: '/color', desc: 'switch color theme' },
  { cmd: '/history', desc: 'resume previous chat' },
  { cmd: '/auto', desc: 'background auto task loop' },
  { cmd: '/config', desc: 'view/update config' },
  { cmd: '/clear', desc: 'clear conversation' },
  { cmd: '/exit', desc: 'exit' },
];

export async function runCLI(cfg) {
  await loadBuiltInTools();
  const custom = await loadCustomTools();
  render.setTheme(cfg.color_theme || 'ocean');

  let agent = new Agent(cfg);
  let currentConversationId = randomUUID();
  const autoState = {
    running: false,
    stopRequested: false,
    loopPromise: null,
    objective: '',
    intervalSec: 30,
    round: 0,
  };
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  readlineCore.emitKeypressEvents(process.stdin, rl);

  console.log(render.banner());
  console.log(render.dimText('  /help  /new  /name  /delete  /tools  /model  /color  /history  /auto  /clear  /exit'));
  if (custom.loaded.length) console.log(render.dimText(`  + ${custom.loaded.length} custom tools loaded`));
  if (custom.failed.length) console.log(render.errorText(`  ! ${custom.failed.length} custom tools failed to load`));
  console.log(render.dimText(`  history: ${historyDir()}`));
  console.log();

  while (true) {
    let input;
    try {
      input = (await promptWithSlashHints(rl)).trim();
    } catch {
      break;
    }
    if (!input) continue;
    await flushPendingResults(currentConversationId);

    if (input.startsWith('/')) {
      const cmdName = input.split(/\s+/)[0].toLowerCase();
      if (autoState.running && cmdName !== '/auto' && cmdName !== '/exit') {
        console.log(render.dimText('Auto mode is running. Only /auto and /exit are allowed now.\n'));
        continue;
      }
      const handled = await handleCommand(input, cfg, agent, rl, currentConversationId, autoState);
      if (handled === 'exit') break;
      if (handled === 'reset') {
        agent = new Agent(cfg);
        const loaded = loadConversation(currentConversationId);
        if (loaded?.messages?.length) agent.loadMessages(loaded.messages, true);
      }
      if (handled?.type === 'switch_conversation') {
        agent = handled.agent;
        currentConversationId = handled.id;
      }
      if (handled?.type === 'clear_saved') {
        currentConversationId = handled.id;
      }
      continue;
    }
    if (autoState.running) {
      console.log(render.dimText('Auto mode is running. Use /auto stop first if you want manual chat.\n'));
      continue;
    }
    agent.setOriginConversationId(currentConversationId);
    await executeAgentTurn(agent, input, rl);
    try {
      saveConversation({
        id: currentConversationId,
        messages: agent.getMessages(),
      });
    } catch {}
    console.log();
  }

  if (autoState.running) {
    autoState.stopRequested = true;
    try { await autoState.loopPromise; } catch {}
  }

  console.log(render.dimText('Bye.'));
  rl.close();
}

async function flushPendingResults(conversationId) {
  const pending = listPendingResults(conversationId);
  if (!pending.length) return;
  const lines = pending.map((item, idx) => {
    const title = item.summary || `任务结果 ${idx + 1}`;
    const when = item.created_at ? new Date(item.created_at).toLocaleString() : '';
    const job = item.job_id ? `job=${item.job_id}` : '';
    return `${idx + 1}. ${title}${when ? ` (${when})` : ''}${job ? ` [${job}]` : ''}`;
  });
  console.log(render.accentText('\n后台任务更新：'));
  console.log(lines.join('\n'));
  console.log();
  markResultsReported(pending.map((item) => item.id));
}

async function executeAgentTurn(agent, input, rl) {
  let spin = render.createSpinner();
  let spinnerActive = false;
  let tokenRight = '(0 tokens)';
  const startSpinner = (label) => {
    spin.stop();
    spin = render.createSpinner(label);
    spin.setRightText(tokenRight);
    spin.start();
    spinnerActive = true;
  };
  const stopSpinner = () => {
    if (!spinnerActive) return;
    spin.stop();
    spinnerActive = false;
  };

  startSpinner();
  let firstToken = true;
  let hasText = false;
  let usageTotal = null;
  let streamedChars = 0;

  for await (const ev of agent.run(input)) {
    if (ev.type === 'text') {
      streamedChars += String(ev.content || '').length;
      if (!usageTotal) {
        const est = Math.ceil(streamedChars / 4);
        tokenRight = `(${est.toLocaleString('en-US')} tokens)`;
        if (spinnerActive) spin.setRightText(tokenRight);
      }

      stopSpinner();
      if (firstToken) {
        console.log();
        firstToken = false;
      }
      hasText = true;
      render.streamWrite(ev.content);
    } else if (ev.type === 'tool_call') {
      stopSpinner();
      if (firstToken) firstToken = false;
      if (hasText) {
        console.log();
        hasText = false;
      }
      console.log(render.toolCallHeader(ev.name));
      console.log(render.toolArgs(ev.arguments));
      startSpinner('running tool');
    } else if (ev.type === 'confirm') {
      stopSpinner();
      const ans = await rl.question('Allow dangerous tool execution? (y/n) > ');
      agent.confirm(ans.trim().toLowerCase() !== 'n');
      startSpinner('running tool');
    } else if (ev.type === 'tool_result') {
      stopSpinner();
      console.log(render.toolResult(ev.result));
      startSpinner();
    } else if (ev.type === 'usage') {
      usageTotal = ev.cumulative;
      tokenRight = `(${Number(usageTotal?.total_tokens || 0).toLocaleString('en-US')} tokens)`;
      if (spinnerActive) spin.setRightText(tokenRight);
    } else if (ev.type === 'error') {
      stopSpinner();
      if (hasText) {
        console.log();
        hasText = false;
      }
      console.log(render.errorText(ev.message));
    }
  }

  stopSpinner();
  process.stderr.write('\r\x1b[K');
  if (hasText) console.log();
  if (usageTotal) console.log(render.tokenUsageLine(usageTotal));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function startAutoLoop({ autoState, agent, rl, getConversationId }) {
  autoState.running = true;
  autoState.stopRequested = false;
  autoState.round = 0;
  autoState.loopPromise = (async () => {
    while (!autoState.stopRequested) {
      autoState.round += 1;
      const isFirst = autoState.round === 1;
      const prompt = isFirst
        ? `自动任务目标：${autoState.objective}\n现在开始执行第 1 轮，并在每轮结束后汇报简短进展。除非收到停止指令，不要结束任务。`
        : `继续执行自动任务目标：${autoState.objective}\n当前为第 ${autoState.round} 轮，请继续执行下一轮。`;

      console.log(render.accentText(`\n[auto] round ${autoState.round} start`));
      agent.setOriginConversationId(getConversationId());
      await executeAgentTurn(agent, prompt, rl);

      try {
        saveConversation({
          id: getConversationId(),
          messages: agent.getMessages(),
        });
      } catch {}

      if (autoState.stopRequested) break;
      console.log(render.dimText(`[auto] sleep ${autoState.intervalSec}s\n`));
      await sleep(autoState.intervalSec * 1000);
    }
  })().finally(() => {
    autoState.running = false;
    autoState.loopPromise = null;
    console.log(render.dimText('[auto] stopped.\n'));
  });
}

async function promptWithSlashHints(rl) {
  return new Promise((resolve, reject) => {
    let lastHint = '';
    let hintShown = false;

    const redraw = (hintText) => {
      if (hintShown) {
        readlineCore.moveCursor(process.stdout, 0, -1);
        readlineCore.clearLine(process.stdout, 0);
        readlineCore.cursorTo(process.stdout, 0);
      }
      readlineCore.clearLine(process.stdout, 0);
      readlineCore.cursorTo(process.stdout, 0);
      if (hintText) {
        process.stdout.write(render.dimText(hintText) + '\n');
        hintShown = true;
      } else {
        hintShown = false;
      }
      rl.setPrompt(render.inputPrompt());
      rl.prompt(true);
    };

    const getHint = () => {
      const line = String(rl.line || '');
      if (!line.startsWith('/')) return '';
      const query = line.toLowerCase();
      const matches = COMMAND_HINTS.filter((item) => item.cmd.startsWith(query)).slice(0, 4);
      if (!matches.length) return '/help  show commands';
      return matches.map((item) => `${item.cmd}  ${item.desc}`).join('    ');
    };

    const onKeypress = () => {
      const next = getHint();
      if (next !== lastHint) {
        lastHint = next;
        redraw(next);
      }
    };

    const cleanup = () => {
      rl.input.removeListener('keypress', onKeypress);
      rl.removeListener('line', onLine);
      rl.removeListener('close', onClose);
      if (hintShown) {
        readlineCore.moveCursor(process.stdout, 0, -1);
        readlineCore.clearLine(process.stdout, 0);
        readlineCore.cursorTo(process.stdout, 0);
      }
    };

    const onLine = (line) => {
      cleanup();
      resolve(line);
    };

    const onClose = () => {
      cleanup();
      reject(new Error('Input closed'));
    };

    rl.on('line', onLine);
    rl.on('close', onClose);
    rl.input.on('keypress', onKeypress);
    redraw(getHint());
  });
}

async function handleCommand(input, cfg, agent, rl, currentConversationId, autoState) {
  const [cmd, ...args] = input.split(/\s+/);

  switch (cmd) {
    case '/exit':
      return 'exit';

    case '/clear':
      agent.reset();
      try {
        clearConversation(currentConversationId);
      } catch {}
      console.log(render.dimText('Conversation cleared.\n'));
      return { type: 'clear_saved', id: currentConversationId };

    case '/help':
      console.log([
        '/new               - Start new conversation',
        '/name              - Rename conversation',
        '/delete            - Delete conversation',
        '/config            - View current config',
        '/config key value  - Update config value',
        '/config max_iterations N - Set iteration cap (-1 means unlimited, default)',
        '/model             - Select model (arrow keys)',
        '/tools             - Browse tools (arrow keys)',
        '/color             - Switch color theme',
        '/history           - Resume previous conversation',
        '/auto start N task - Start background task loop every N seconds',
        '/auto stop         - Stop background task loop',
        '/auto status       - Show background task status',
        '/clear             - Clear conversation',
        '/exit              - Exit',
      ].join('\n') + '\n');
      return;

    case '/new': {
      const nextAgent = new Agent(cfg);
      const nextId = randomUUID();
      console.log(render.dimText('Started new conversation.\n'));
      return { type: 'switch_conversation', id: nextId, agent: nextAgent };
    }

    case '/tools': {
      const registry = getAllTools();
      const names = Object.keys(registry).sort();
      if (!names.length) {
        console.log(render.dimText('No tools loaded.\n'));
        return;
      }
      const idx = await selectWithArrows(rl, {
        title: 'Select tool',
        options: names,
        pageSize: 14,
        getLabel: (name) => `${name}${registry[name]?.dangerous ? '  [dangerous]' : ''}`,
      });
      if (idx == null) {
        console.log(render.dimText('Canceled.\n'));
        return;
      }

      const selectedName = names[idx];
      const info = registry[selectedName];
      const required = info?.parameters?.required || [];
      const props = Object.keys(info?.parameters?.properties || {});
      console.log(render.accentText(`\n${selectedName}`));
      if (info?.description) console.log(render.dimText(info.description));
      console.log(render.dimText(`dangerous: ${Boolean(info?.dangerous)}`));
      console.log(render.dimText(`params: ${props.join(', ') || '(none)'}`));
      console.log(render.dimText(`required: ${required.join(', ') || '(none)'}\n`));
      return;
    }

    case '/history': {
      const items = listConversations();
      const options = [...items];
      if (!options.length) {
        console.log(render.dimText('No history found. Use /new to start.\n'));
        return;
      }
      const idx = await selectWithArrows(rl, {
        title: 'Conversation history',
        options,
        pageSize: 12,
        getLabel: (item) => {
          if (item.id === '__new__') return item.title;
          const date = item.updatedAt ? new Date(item.updatedAt).toLocaleString() : '';
          return `${item.title}${date ? `  (${date})` : ''}`;
        },
      });
      if (idx == null) {
        console.log(render.dimText('Canceled.\n'));
        return;
      }
      const selected = options[idx];
      const loaded = loadConversation(selected.id);
      if (!loaded) {
        console.log(render.errorText('Failed to load conversation.\n'));
        return;
      }
      const nextAgent = new Agent(cfg);
      nextAgent.loadMessages(loaded.messages || [], true);
      console.log(render.dimText(`Resumed: ${loaded.title}\n`));
      return { type: 'switch_conversation', id: loaded.id, agent: nextAgent };
    }

    case '/name': {
      const items = listConversations();
      if (!items.length) {
        console.log(render.dimText('No history found.\n'));
        return;
      }
      const currentIndex = Math.max(0, items.findIndex((item) => item.id === currentConversationId));
      const idx = await selectWithArrows(rl, {
        title: 'Rename conversation',
        options: items,
        initialIndex: currentIndex,
        pageSize: 12,
        getLabel: (item) => item.title,
      });
      if (idx == null) {
        console.log(render.dimText('Canceled.\n'));
        return;
      }
      const picked = items[idx];
      const title = (await rl.question('New name: ')).trim();
      if (!title) {
        console.log(render.dimText('Canceled.\n'));
        return;
      }
      const renamed = renameConversation(picked.id, title);
      if (!renamed) {
        console.log(render.errorText('Rename failed.\n'));
        return;
      }
      console.log(render.dimText(`Renamed to "${renamed.title}".\n`));
      return;
    }

    case '/delete': {
      const items = listConversations();
      if (!items.length) {
        console.log(render.dimText('No history found.\n'));
        return;
      }
      const currentIndex = Math.max(0, items.findIndex((item) => item.id === currentConversationId));
      const idx = await selectWithArrows(rl, {
        title: 'Delete conversation',
        options: items,
        initialIndex: currentIndex,
        pageSize: 12,
        getLabel: (item) => item.title,
      });
      if (idx == null) {
        console.log(render.dimText('Canceled.\n'));
        return;
      }
      const picked = items[idx];
      const confirm = (await rl.question(`Delete "${picked.title}"? (y/n): `)).trim().toLowerCase();
      if (confirm !== 'y' && confirm !== 'yes') {
        console.log(render.dimText('Canceled.\n'));
        return;
      }
      const ok = deleteConversation(picked.id);
      if (!ok) {
        console.log(render.errorText('Delete failed.\n'));
        return;
      }
      if (picked.id === currentConversationId) {
        const nextAgent = new Agent(cfg);
        const nextId = randomUUID();
        console.log(render.dimText('Deleted current conversation. Switched to new conversation.\n'));
        return { type: 'switch_conversation', id: nextId, agent: nextAgent };
      }
      console.log(render.dimText('Deleted.\n'));
      return;
    }

    case '/color': {
      const names = render.getThemeNames();
      const current = render.getThemeName();
      const initialIndex = Math.max(0, names.findIndex((name) => name === current));
      const idx = await selectWithArrows(rl, {
        title: 'Select color theme',
        options: names,
        initialIndex,
        pageSize: 8,
        getLabel: (name) => `${name}${name === current ? '  (current)' : ''}`,
        onHighlight: (name) => { render.setTheme(name); },
      });
      if (idx == null) {
        render.setTheme(current);
        console.log(render.dimText('Canceled.\n'));
        return;
      }
      const selected = names[idx];
      render.setTheme(selected);
      cfg.color_theme = selected;
      saveConfig(cfg);
      console.log(render.dimText(`Theme changed to ${selected}\n`));
      return;
    }

    case '/config':
      if (args.length === 0) {
        const { api_key, ...rest } = cfg;
        console.log(JSON.stringify({ ...rest, api_key: api_key ? `***${api_key.slice(-4)}` : '' }, null, 2) + '\n');
        return;
      }
      if (args.length >= 2) {
        const key = args[0];
        const val = args.slice(1).join(' ');
        if (key in cfg) {
          cfg[key] = Number.isNaN(Number(val))
            ? (val === 'true' ? true : val === 'false' ? false : val)
            : Number(val);
          saveConfig(cfg);
          console.log(render.dimText(`Updated ${key}\n`));
          return 'reset';
        }
        console.log(render.errorText(`Unknown config key: ${key}\n`));
        return;
      }
      console.log(render.errorText('Usage: /config [key value]\n'));
      return;

    case '/auto': {
      const sub = String(args[0] || '').toLowerCase();
      if (sub === 'status') {
        if (!autoState.running) {
          console.log(render.dimText('Auto mode: stopped.\n'));
          return;
        }
        console.log(render.dimText(`Auto mode: running, interval=${autoState.intervalSec}s, round=${autoState.round}`));
        console.log(render.dimText(`Objective: ${autoState.objective}\n`));
        return;
      }

      if (sub === 'stop') {
        if (!autoState.running) {
          console.log(render.dimText('Auto mode is not running.\n'));
          return;
        }
        autoState.stopRequested = true;
        console.log(render.dimText('Stopping auto mode... current round will finish first.\n'));
        return;
      }

      if (sub === 'start') {
        if (autoState.running) {
          console.log(render.errorText('Auto mode already running. Use /auto stop first.\n'));
          return;
        }
        const interval = Number(args[1]);
        if (!Number.isFinite(interval) || interval <= 0) {
          console.log(render.errorText('Usage: /auto start <interval_seconds> <task>\n'));
          return;
        }
        const objective = args.slice(2).join(' ').trim();
        if (!objective) {
          console.log(render.errorText('Usage: /auto start <interval_seconds> <task>\n'));
          return;
        }

        autoState.intervalSec = Math.min(3600, Math.max(1, Math.trunc(interval)));
        autoState.objective = objective;
        startAutoLoop({
          autoState,
          agent,
          rl,
          getConversationId: () => currentConversationId,
        });
        console.log(render.dimText(`Auto mode started: every ${autoState.intervalSec}s\n`));
        return;
      }

      console.log(render.errorText('Usage: /auto <start|stop|status>\n'));
      return;
    }

    case '/model':
      try {
        console.log(render.dimText('Fetching models...'));
        const client = new Client(cfg);
        const models = await client.listModels();
        if (!models.length) {
          console.log('No models found.\n');
          return;
        }

        const currentIndex = Math.max(0, models.findIndex((model) => model === cfg.model));
        const idx = await selectWithArrows(rl, {
          title: 'Select model',
          options: models,
          initialIndex: currentIndex,
          pageSize: 12,
          getLabel: (model) => `${model}${model === cfg.model ? '  (current)' : ''}`,
        });
        if (idx == null) {
          console.log(render.dimText('No change.\n'));
          return;
        }
        if (idx >= 0 && idx < models.length) {
          cfg.model = models[idx];
          saveConfig(cfg);
          console.log(render.dimText(`Switched to ${cfg.model}\n`));
          return 'reset';
        }
        console.log(render.dimText('No change.\n'));
      } catch (e) {
        console.log(render.errorText(`Failed to fetch models: ${e.message}\n`));
      }
      return;

    default:
      console.log(render.dimText(`Unknown command: ${cmd}. Use /help.\n`));
  }
}

async function selectWithArrows(
  rl,
  { title, options, initialIndex = 0, pageSize = 10, getLabel = (v) => String(v), onHighlight = null },
) {
  if (!Array.isArray(options) || !options.length) return null;

  return new Promise((resolve) => {
    const input = rl.input;
    const isTTY = Boolean(input && input.isTTY && typeof input.setRawMode === 'function');
    const previousRaw = isTTY ? input.isRaw : false;
    let selected = Math.min(Math.max(initialIndex, 0), options.length - 1);
    let renderedLines = 0;

    const clearRendered = () => {
      for (let i = 0; i < renderedLines; i++) {
        readlineCore.moveCursor(process.stdout, 0, -1);
        readlineCore.clearLine(process.stdout, 0);
        readlineCore.cursorTo(process.stdout, 0);
      }
      renderedLines = 0;
    };

    const draw = () => {
      if (typeof onHighlight === 'function') onHighlight(options[selected], selected);
      clearRendered();
      const total = options.length;
      const maxSize = Math.max(5, pageSize);
      const start = Math.max(0, Math.min(selected - Math.floor(maxSize / 2), total - maxSize));
      const end = Math.min(total, start + maxSize);

      process.stdout.write(render.dimText(`${title}  ([up/down] move, Enter confirm, Esc cancel)\n`));
      renderedLines++;

      if (start > 0) {
        process.stdout.write(render.dimText('  ...\n'));
        renderedLines++;
      }

      for (let i = start; i < end; i++) {
        const active = i === selected;
        const label = getLabel(options[i], i);
        const line = active
          ? render.menuActive(` > ${label} `)
          : render.menuInactive(`   ${label}`);
        process.stdout.write(`${line}\n`);
        renderedLines++;
      }

      if (end < total) {
        process.stdout.write(render.dimText('  ...\n'));
        renderedLines++;
      }
    };

    const cleanup = () => {
      input.removeListener('keypress', onKeypress);
      clearRendered();
      if (isTTY) input.setRawMode(previousRaw);
    };

    const onKeypress = (_str, key = {}) => {
      if (key.name === 'up') {
        selected = selected > 0 ? selected - 1 : options.length - 1;
        draw();
        return;
      }
      if (key.name === 'down') {
        selected = selected < options.length - 1 ? selected + 1 : 0;
        draw();
        return;
      }
      if (key.name === 'return' || key.name === 'enter') {
        cleanup();
        resolve(selected);
        return;
      }
      if (key.name === 'escape') {
        cleanup();
        resolve(null);
      }
    };

    if (isTTY) input.setRawMode(true);
    input.on('keypress', onKeypress);
    draw();
  });
}
