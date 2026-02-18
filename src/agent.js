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

  return `你是 StarBot，本地自主执行型 AI 助手。优先中文回复，简洁直接。
<environment>
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
1) 直接调用工具完成任务。
2) 复杂任务可链式调用多个工具。
3) 执行失败先分析再重试。
4) 每步完成后给出简短结论。
</behavior>`;
}

export class Agent {
  constructor(cfg) {
    this.systemPrompt = buildSystemPrompt();
    this.client = new Client(cfg);
    this.conv = new Conversation(this.systemPrompt);
    this.maxIterations = cfg.max_iterations;
    this.permissionMode = cfg.permission_mode || 'maximum';
    this.confirmDangerous = this.permissionMode === 'maximum' ? false : cfg.confirm_dangerous;
    this._onConfirm = null;
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
        content: '继续历史对话模式：请先阅读并参考以上历史消息，再回答用户当前问题。',
      });
    }
    this.conv = new Conversation();
    this.conv.setMessages(merged);
  }

  async *run(userInput) {
    this.conv.addUser(userInput);
    const tools = getOpenAITools();

    for (let i = 0; i < this.maxIterations; i++) {
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
          const approved = await new Promise((resolve) => { this._onConfirm = resolve; });
          if (!approved) {
            const result = '[user denied execution]';
            this.conv.addToolResult(tc.id, result);
            yield { type: 'tool_result', name: tc.name, result, id: tc.id };
            continue;
          }
        }

        let result;
        try {
          result = await callTool(tc.name, tc.arguments);
        } catch (e) {
          result = `[error] ${e.message}`;
        }
        this.conv.addToolResult(tc.id, result);
        yield { type: 'tool_result', name: tc.name, result, id: tc.id };
      }
    }

    yield { type: 'error', message: 'Max iterations reached' };
  }

  confirm(approved) {
    if (this._onConfirm) {
      this._onConfirm(approved);
      this._onConfirm = null;
    }
  }

  reset() {
    this.conv.clear();
    this.usageTotal = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
  }
}
