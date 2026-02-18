import { hasTool, removeTool, tool } from './registry.js';
import { registerDynamicTool, saveDynamicToolSpec, getCustomToolsDir } from './dynamic_tooling.js';

tool('create_tool', 'Create a new tool at runtime that the AI can then use. The tool code is JavaScript executed in Node.js. This allows the AI to extend its own capabilities dynamically.', {
  properties: {
    name: { type: 'string', description: 'Tool name (snake_case)' },
    description: { type: 'string', description: 'What the tool does' },
    parameters: { type: 'object', description: 'JSON Schema properties object, e.g. {"input":{"type":"string","description":"..."}}' },
    required_params: { type: 'array', description: 'Array of required parameter names', items: { type: 'string' } },
    code: { type: 'string', description: 'JS function body. Receives destructured params. Use return for output. Can use require() and async/await.' },
    dangerous: { type: 'boolean', description: 'Whether tool needs confirmation (default false)' },
    persist: { type: 'boolean', description: 'Persist tool to disk for future sessions (default true)' },
    overwrite: { type: 'boolean', description: 'Overwrite existing same-name persisted tool (default true)' },
  },
  required: ['name', 'description', 'parameters', 'code'],
}, true, async ({ name, description, parameters, required_params = [], code, dangerous = false, persist = true, overwrite = true }) => {
  try {
    if (hasTool(name)) removeTool(name);
    const spec = { name, description, parameters, required_params, code, dangerous };
    const toolName = registerDynamicTool(spec, true);
    if (!persist) return `Tool "${toolName}" created (session only).`;
    const file = saveDynamicToolSpec(spec, overwrite);
    return `Tool "${toolName}" created and persisted to ${file}. It will auto-load on startup from ${getCustomToolsDir()}.`;
  } catch (e) {
    return `[error] ${e.message}`;
  }
});
