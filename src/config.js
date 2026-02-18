import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import readline from 'readline/promises';

const CONFIG_DIR = join(homedir(), '.starbot');
const CONFIG_FILE = join(CONFIG_DIR, 'config.json');

const DEFAULTS = {
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4o',
  color_theme: 'ocean',
  temperature: 0.7,
  max_tokens: 4096,
  permission_mode: 'maximum',
  system_prompt: null, // built dynamically with env context
  max_iterations: 30,
  confirm_dangerous: false,
};

export function loadConfig() {
  let cfg = { ...DEFAULTS };
  if (existsSync(CONFIG_FILE)) {
    try {
      const file = JSON.parse(readFileSync(CONFIG_FILE, 'utf-8'));
      cfg = { ...cfg, ...file };
    } catch {}
  }
  // These always use built-in values (not saved overrides)
  cfg.permission_mode = DEFAULTS.permission_mode;
  cfg.system_prompt = DEFAULTS.system_prompt;
  cfg.confirm_dangerous = DEFAULTS.confirm_dangerous;
  cfg.max_iterations = DEFAULTS.max_iterations;
  // env overrides
  if (process.env.STARBOT_API_KEY) cfg.api_key = process.env.STARBOT_API_KEY;
  if (process.env.STARBOT_BASE_URL) cfg.base_url = process.env.STARBOT_BASE_URL;
  if (process.env.STARBOT_MODEL) cfg.model = process.env.STARBOT_MODEL;
  return cfg;
}

export function saveConfig(cfg) {
  mkdirSync(CONFIG_DIR, { recursive: true });
  const { system_prompt, max_iterations, confirm_dangerous, ...rest } = cfg;
  const toSave = { ...rest, system_prompt, max_iterations, confirm_dangerous };
  writeFileSync(CONFIG_FILE, JSON.stringify(toSave, null, 2), 'utf-8');
}

export async function setupWizard(cfg) {
  if (cfg.api_key) return cfg;
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  try {
    console.log('='.repeat(50));
    console.log('  StarBot 首次运行配置');
    console.log('='.repeat(50));
    const apiKey = (await rl.question('\nAPI Key: ')).trim();
    if (!apiKey) { console.log('未输入 API Key，退出。'); process.exit(1); }
    const baseUrl = (await rl.question(`Base URL [${cfg.base_url}]: `)).trim();
    const model = (await rl.question(`模型名称 [${cfg.model}]: `)).trim();
    cfg.api_key = apiKey;
    if (baseUrl) cfg.base_url = baseUrl;
    if (model) cfg.model = model;
    saveConfig(cfg);
    console.log(`\n配置已保存到 ${CONFIG_FILE}\n`);
    return cfg;
  } finally {
    rl.close();
  }
}
