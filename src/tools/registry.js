const _tools = {};

export function tool(name, description, params, dangerous = false, fn) {
  _tools[name] = { name, description, parameters: { type: 'object', properties: params.properties, required: params.required || [] }, dangerous, fn };
}

export function removeTool(name) {
  delete _tools[name];
}

export function getOpenAITools() {
  return Object.values(_tools).map(t => ({
    type: 'function',
    function: { name: t.name, description: t.description, parameters: t.parameters },
  }));
}

export async function callTool(name, argsStr, context = {}) {
  if (!_tools[name]) return JSON.stringify({ error: `Unknown tool: ${name}` });
  const args = typeof argsStr === 'string' ? JSON.parse(argsStr) : argsStr;
  const result = await _tools[name].fn(args, context || {});
  return typeof result === 'string' ? result : JSON.stringify(result, null, 2);
}

export function isDangerous(name) {
  return _tools[name]?.dangerous ?? false;
}

export function getAllTools() { return _tools; }
export function hasTool(name) { return name in _tools; }
