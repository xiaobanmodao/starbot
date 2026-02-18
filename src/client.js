import OpenAI from 'openai';

export class Client {
  constructor(cfg) {
    this.client = new OpenAI({
      apiKey: cfg.api_key || 'sk-placeholder',
      baseURL: cfg.base_url,
    });
    this.model = cfg.model;
    this.temperature = cfg.temperature;
    this.max_tokens = cfg.max_tokens;
  }

  async *chatStream(messages, tools = null) {
    const opts = {
      model: this.model,
      messages,
      temperature: this.temperature,
      max_tokens: this.max_tokens,
      stream: true,
      stream_options: { include_usage: true },
    };
    if (tools?.length) opts.tools = tools;
    const stream = await this.client.chat.completions.create(opts);
    for await (const chunk of stream) {
      yield chunk;
    }
  }

  async listModels() {
    const resp = await this.client.models.list();
    const models = [];
    for await (const m of resp) models.push(m.id);
    return models.sort();
  }
}
