import { platform, homedir, hostname, userInfo } from 'os';
import { cwd } from 'process';
import { Client } from './client.js';
import { Conversation } from './conversation.js';
import { getOpenAITools, callTool, isDangerous } from './tools/registry.js';

function buildSystemPrompt() {
  const os = platform() === 'win32' ? 'Windows' : platform() === 'darwin' ? 'macOS' : 'Linux';
  const shell = platform() === 'win32' ? 'cmd/powershell' : 'bash/zsh';
  const user = userInfo().username;
  const dir = cwd();
  const date = new Date().toLocaleDateString('zh-CN');

  return `浣犳槸 StarBot锛屾湰鍦拌嚜涓绘墽琛屽瀷 AI 鍔╂墜銆備紭鍏堜腑鏂囧洖澶嶏紝绠€娲佺洿鎺ャ€?<environment>
os: ${os}
shell: ${shell}
user: ${user}
host: ${hostname()}
home: ${homedir()}
cwd: ${dir}
date: ${date}
</environment>
<permissions>
mode: maximum
dangerous_tools: auto_approved
tool_creation: allowed_and_persistent
</permissions>
<behavior>
1) 鐩存帴璋冪敤宸ュ叿瀹屾垚浠诲姟銆?2) 澶嶆潅浠诲姟鍙摼寮忚皟鐢ㄥ涓伐鍏枫€?3) 鎵ц澶辫触鍏堝垎鏋愬啀閲嶈瘯銆?4) 姣忔瀹屾垚鍚庣粰鍑虹畝鐭粨璁恒€?</behavior>
<long_running>
For monitoring tasks, keep looping with tools and use wait_seconds between checks until user asks to stop.
When user asks "keep doing this automatically without me", create unattended jobs with unattended_watch_delete_file and ensure daemon is running.
Default to pure programmatic automation; enable AI exception analysis only when rules are insufficient or conditions conflict.
</long_running>`;
}

export class Agent {
  constructor(cfg) {
    this.systemPrompt = buildSystemPrompt();
    this.client = new Client(cfg);
    this.conv = new Conversation(this.systemPrompt);
    this.maxIterations = Number.isFinite(Number(cfg.max_iterations))
      ? Math.trunc(Number(cfg.max_iterations))
      : -1;
    this.permissionMode = cfg.permission_mode || 'maximum';
    this.confirmDangerous = this.permissionMode === 'maximum' ? false : cfg.confirm_dangerous;
    this._onConfirm = null;
    this._pendingConfirmDecision = null;
    this.originConversationId = null;
    this.usageTotal = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
  }

  getMessages() {
    return this.conv.getMessages();
  }

  loadMessages(messages = [], withContinueReminder = true) {
    const list = Array.isArray(messages) ? messages : [];
    if (!list.length) {
      this.conv = new Conversation(this.systemPrompt);
      return;
    }
    const hasSystem = list.some((message) => message?.role === 'system');
    const merged = hasSystem ? [...list] : [{ role: 'system', content: this.systemPrompt }, ...list];
    if (withContinueReminder) {
      merged.push({
        role: 'system',
        content: 'Continue the prior conversation context before answering the latest user request.',
      });
    }
    this.conv = new Conversation();
    this.conv.setMessages(merged);
  }

  async *run(userInput) {
    this.conv.addUser(userInput);
    const tools = getOpenAITools();

    let i = 0;
    while (this.maxIterations < 0 || i < this.maxIterations) {
      i += 1;
      const textParts = [];
      const tcMap = {};
      let requestUsage = null;

      for await (const chunk of this.client.chatStream(this.conv.getMessages(), tools.length ? tools : null)) {
        if (chunk?.usage) requestUsage = chunk.usage;

        const delta = chunk.choices?.[0]?.delta;
        if (!delta) continue;
        if (delta.content) {
          textParts.push(delta.content);
          yield { type: 'text', content: delta.content };
        }
        if (delta.tool_calls) {
          for (const tc of delta.tool_calls) {
            const idx = tc.index;
            if (!tcMap[idx]) tcMap[idx] = { id: '', name: '', arguments: '' };
            if (tc.id) tcMap[idx].id = tc.id;
            if (tc.function?.name) tcMap[idx].name = tc.function.name;
            if (tc.function?.arguments) tcMap[idx].arguments += tc.function.arguments;
          }
        }
      }

      if (requestUsage) {
        this.usageTotal.prompt_tokens += requestUsage.prompt_tokens || 0;
        this.usageTotal.completion_tokens += requestUsage.completion_tokens || 0;
        this.usageTotal.total_tokens += requestUsage.total_tokens || 0;
        yield {
          type: 'usage',
          usage: requestUsage,
          cumulative: { ...this.usageTotal },
        };
      }

      const fullText = textParts.join('') || null;
      const tcKeys = Object.keys(tcMap);
      if (!tcKeys.length) {
        this.conv.addAssistant(fullText);
        return;
      }

      const tcList = tcKeys.map((key) => ({
        id: tcMap[key].id,
        type: 'function',
        function: { name: tcMap[key].name, arguments: tcMap[key].arguments },
      }));
      this.conv.addAssistant(fullText, tcList);

      for (const tc of Object.values(tcMap)) {
        yield { type: 'tool_call', name: tc.name, arguments: tc.arguments, id: tc.id };

        if (this.confirmDangerous && isDangerous(tc.name)) {
          yield { type: 'confirm', name: tc.name, arguments: tc.arguments, id: tc.id };
          let approved;
          if (typeof this._pendingConfirmDecision === 'boolean') {
            approved = this._pendingConfirmDecision;
            this._pendingConfirmDecision = null;
          } else {
            approved = await new Promise((resolve) => { this._onConfirm = resolve; });
          }
          if (!approved) {
            const result = '[user denied execution]';
            this.conv.addToolResult(tc.id, result);
            yield { type: 'tool_result', name: tc.name, result, id: tc.id };
            continue;
          }
        }

        let result;
        try {
          result = await callTool(tc.name, tc.arguments, {
            origin_conversation_id: this.originConversationId,
          });
        } catch (e) {
          result = `[error] ${e.message}`;
        }
        this.conv.addToolResult(tc.id, result);
        yield { type: 'tool_result', name: tc.name, result, id: tc.id };
      }
    }

    yield {
      type: 'error',
      message: 'Max iterations reached. Set /config max_iterations -1 for continuous tasks.',
    };
  }

  confirm(approved) {
    if (this._onConfirm) {
      this._onConfirm(approved);
      this._onConfirm = null;
      return;
    }
    this._pendingConfirmDecision = Boolean(approved);
  }

  setOriginConversationId(id) {
    this.originConversationId = id ? String(id) : null;
  }

  reset() {
    this.conv.clear();
    this._onConfirm = null;
    this._pendingConfirmDecision = null;
    this.usageTotal = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
  }
}

