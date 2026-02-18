import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import { createRequire } from 'module';
import { hasTool, removeTool, tool } from './registry.js';

export function getCustomToolsDir() {
  return process.env.STARBOT_CUSTOM_TOOLS_DIR || join(homedir(), '.starbot', 'tools');
}

function normalizeName(name = '') {
  return String(name).toLowerCase().replace(/[^a-z0-9_]/g, '_');
}

function buildDynamicExecutor(code) {
  return async (args) => {
    try {
      const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
      const req = createRequire(import.meta.url);
      const fn = new AsyncFunction('args', 'require', `with(args){${code}}`);
      const result = await fn(args, req);
      if (result === undefined) return '(no output)';
      return typeof result === 'string' ? result : JSON.stringify(result, null, 2);
    } catch (e) {
      return `[error] ${e.message}`;
    }
  };
}

export function registerDynamicTool(spec, replace = true) {
  const name = normalizeName(spec?.name || '');
  if (!name) throw new Error('Invalid tool name');

  const parameters = spec.parameters || {};
  const required = Array.isArray(spec.required_params) ? spec.required_params : [];
  const dangerous = Boolean(spec.dangerous);
  const description = String(spec.description || '').trim() || `Dynamic tool ${name}`;
  const code = String(spec.code || '');
  if (!code.trim()) throw new Error('Tool code is empty');

  if (hasTool(name) && replace) removeTool(name);
  if (hasTool(name) && !replace) throw new Error(`Tool already exists: ${name}`);

  tool(
    name,
    description,
    { properties: parameters, required },
    dangerous,
    buildDynamicExecutor(code),
  );

  return name;
}

export function saveDynamicToolSpec(spec, overwrite = true) {
  const dir = getCustomToolsDir();
  mkdirSync(dir, { recursive: true });
  const name = normalizeName(spec?.name || '');
  if (!name) throw new Error('Invalid tool name');
  const file = join(dir, `${name}.json`);
  if (!overwrite && existsSync(file)) throw new Error(`Tool file exists: ${file}`);
  writeFileSync(file, JSON.stringify({
    name,
    description: spec.description,
    parameters: spec.parameters,
    required_params: spec.required_params || [],
    code: spec.code,
    dangerous: Boolean(spec.dangerous),
  }, null, 2), 'utf-8');
  return file;
}

export function loadPersistedTools() {
  const dir = getCustomToolsDir();
  if (!existsSync(dir)) return { loaded: [], failed: [] };
  const loaded = [];
  const failed = [];

  for (const name of readdirSync(dir)) {
    if (!name.toLowerCase().endsWith('.json')) continue;
    const full = join(dir, name);
    try {
      const spec = JSON.parse(readFileSync(full, 'utf-8'));
      const toolName = registerDynamicTool(spec, true);
      loaded.push({ name: toolName, file: full });
    } catch (e) {
      failed.push({ file: full, error: e.message });
    }
  }

  return { loaded, failed };
}
