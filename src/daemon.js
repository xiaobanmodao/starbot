import { runAutomationDaemon } from './automation/runner/engine.js';

export async function runDaemon() {
  await runAutomationDaemon();
}
