export class Conversation {
  constructor(systemPrompt = '') {
    this.messages = [];
    this.maxToolOutputChars = 2400;
    this.maxHistoryMessages = 80;
    this.historySummaryRole = 'system';
    if (systemPrompt) this.messages.push({ role: 'system', content: systemPrompt });
  }

  addUser(content) {
    this.messages.push({ role: 'user', content });
  }

  addAssistant(content = null, toolCalls = null) {
    const msg = { role: 'assistant' };
    if (content) msg.content = content;
    if (toolCalls) msg.tool_calls = toolCalls;
    this.messages.push(msg);
    this.compactHistory();
  }

  addToolResult(toolCallId, content) {
    this.messages.push({
      role: 'tool',
      tool_call_id: toolCallId,
      content: this.compactToolOutput(content),
    });
    this.compactHistory();
  }

  getMessages() {
    return this.messages;
  }

  setMessages(messages = []) {
    this.messages = Array.isArray(messages) ? messages : [];
    this.compactHistory();
  }

  clear() {
    this.messages = this.messages.filter((message) => message.role === 'system');
  }

  compactToolOutput(content) {
    const text = String(content ?? '');
    if (text.length <= this.maxToolOutputChars) return text;
    const head = text.slice(0, 1400);
    const tail = text.slice(-600);
    return `${head}\n\n...[tool output compressed ${text.length - 2000} chars]...\n\n${tail}`;
  }

  compactHistory() {
    if (this.messages.length <= this.maxHistoryMessages) return;
    const system = this.messages.filter((message) => message.role === 'system');
    const nonSystem = this.messages.filter((message) => message.role !== 'system');
    const keep = nonSystem.slice(-this.maxHistoryMessages);
    const dropped = nonSystem.slice(0, Math.max(0, nonSystem.length - keep.length));
    const summary = this.buildSummary(dropped);
    const baseSystem = system.filter((message) => !String(message.content || '').startsWith('[history_summary]'));
    if (summary) {
      baseSystem.push({
        role: this.historySummaryRole,
        content: `[history_summary]\n${summary}`,
      });
    }
    this.messages = [...baseSystem, ...keep];
  }

  buildSummary(messages = []) {
    if (!messages.length) return '';
    const lines = [];
    for (const message of messages) {
      const role = message.role || 'unknown';
      if (role === 'tool') continue;
      const text = String(message.content || '').replace(/\s+/g, ' ').trim();
      if (!text) continue;
      lines.push(`${role}: ${text.slice(0, 160)}`);
      if (lines.length >= 18) break;
    }
    const summary = lines.join('\n');
    return summary.slice(0, 2000);
  }
}
