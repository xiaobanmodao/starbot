import { runAutomationDaemon } from './automation/runner/engine.js';

export async function runDaemon(cfg = null) {
  await runAutomationDaemon(cfg);
}
