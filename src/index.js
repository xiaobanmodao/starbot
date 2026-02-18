import readline from 'readline/promises';
import * as readlineCore from 'readline';
import chalk from 'chalk';
import { stdin as input, stdout as output, argv } from 'process';
import { loadConfig, setupWizard } from './config.js';
import { runCLI } from './cli.js';
import { runWeb } from './web/server.js';
import { runDaemon } from './daemon.js';
import {
  createFileDeleteTask,
  listTasks,
  removeTask,
  tasksFilePath,
  updateTask,
} from './automation/store/tasks.js';

function getArg(flag) {
  const idx = argv.indexOf(flag);
  if (idx < 0) return null;
  return argv[idx + 1] ?? null;
}

function hasArg(flag) {
  return argv.includes(flag);
}

function parseModeFromArgs() {
  if (hasArg('--daemon')) return 'daemon';
  if (hasArg('--web')) return 'web';
  if (hasArg('--cli')) return 'cli';
  return null;
}

function printJobs() {
  const jobs = listTasks();
  if (!jobs.length) {
    console.log('No daemon jobs found.');
    console.log(`Jobs file: ${tasksFilePath()}`);
    return;
  }
  console.log(`Jobs file: ${tasksFilePath()}`);
  for (const job of jobs) {
    console.log(
      [
        `id=${job.id}`,
        `task_id=${job.task_id}`,
        `enabled=${Boolean(job.enabled)}`,
        `interval=${job.interval_sec}s`,
        `last_status=${job.last_status || 'idle'}`,
      ].join(' | '),
    );
  }
}

function handleJobCommands() {
  if (hasArg('--job-list')) {
    printJobs();
    return true;
  }

  if (hasArg('--job-add')) {
    const taskId = getArg('--task-id') || getArg('--name');
    const path = getArg('--path');
    const interval = getArg('--interval');
    const origin = getArg('--origin');
    const endAt = getArg('--end-at');
    if (!taskId || !path || !interval || !origin) {
      console.log('Usage: --job-add --task-id "<id>" --path "<absolute_path>" --interval <seconds> --origin <conversation_id> [--end-at <ISO8601>]');
      return true;
    }
    const job = createFileDeleteTask({
      task_id: taskId,
      file_path: path,
      interval_sec: interval,
      origin_conversation_id: origin,
      end_at: endAt || null,
      notify: true,
    });
    console.log(`Job created: ${job.id}`);
    return true;
  }

  if (hasArg('--job-remove')) {
    const id = getArg('--job-remove');
    if (!id) {
      console.log('Usage: --job-remove <job_id>');
      return true;
    }
    const ok = removeTask(id);
    console.log(ok ? `Job removed: ${id}` : `Job not found: ${id}`);
    return true;
  }

  if (hasArg('--job-enable')) {
    const id = getArg('--job-enable');
    if (!id) {
      console.log('Usage: --job-enable <job_id>');
      return true;
    }
    const updated = updateTask(id, { enabled: true, status: 'running' });
    console.log(`Job enabled: ${updated.id}`);
    return true;
  }

  if (hasArg('--job-disable')) {
    const id = getArg('--job-disable');
    if (!id) {
      console.log('Usage: --job-disable <job_id>');
      return true;
    }
    const updated = updateTask(id, { enabled: false });
    console.log(`Job disabled: ${updated.id}`);
    return true;
  }

  return false;
}

async function chooseModeWithArrows() {
  const rl = readline.createInterface({ input, output });
  readlineCore.emitKeypressEvents(input, rl);

  const options = [
    { value: 'cli', label: 'CLI' },
    { value: 'web', label: 'Web (auto open browser)' },
    { value: 'daemon', label: 'Daemon (run jobs in background)' },
  ];

  const idx = await selectWithArrows(rl, {
    title: 'Select mode',
    options,
    initialIndex: 0,
    getLabel: (item) => item.label,
  });

  rl.close();
  if (idx == null) return 'cli';
  return options[idx].value;
}

async function selectWithArrows(rl, { title, options, initialIndex = 0, getLabel = (v) => String(v) }) {
  if (!options.length) return null;

  return new Promise((resolve) => {
    const inputStream = rl.input;
    const isTTY = Boolean(inputStream && inputStream.isTTY && typeof inputStream.setRawMode === 'function');
    const previousRaw = isTTY ? inputStream.isRaw : false;
    let selected = Math.min(Math.max(initialIndex, 0), options.length - 1);
    let renderedLines = 0;

    const clearRendered = () => {
      for (let i = 0; i < renderedLines; i++) {
        readlineCore.moveCursor(output, 0, -1);
        readlineCore.clearLine(output, 0);
        readlineCore.cursorTo(output, 0);
      }
      renderedLines = 0;
    };

    const draw = () => {
      clearRendered();
      output.write(chalk.gray(`${title}  ([up/down] move, Enter confirm)\n`));
      renderedLines++;
      for (let i = 0; i < options.length; i++) {
        const active = i === selected;
        const text = getLabel(options[i], i);
        const line = active ? chalk.whiteBright.bgBlue(` > ${text} `) : chalk.gray(`   ${text}`);
        output.write(`${line}\n`);
        renderedLines++;
      }
    };

    const cleanup = () => {
      inputStream.removeListener('keypress', onKeypress);
      clearRendered();
      if (isTTY) inputStream.setRawMode(previousRaw);
    };

    const onKeypress = (_str, key = {}) => {
      if (key.name === 'up') {
        selected = selected > 0 ? selected - 1 : options.length - 1;
        draw();
        return;
      }
      if (key.name === 'down') {
        selected = selected < options.length - 1 ? selected + 1 : 0;
        draw();
        return;
      }
      if (key.name === 'return' || key.name === 'enter') {
        cleanup();
        resolve(selected);
      }
    };

    if (isTTY) inputStream.setRawMode(true);
    inputStream.on('keypress', onKeypress);
    draw();
  });
}

async function main() {
  if (hasArg('--job-list') || hasArg('--job-add') || hasArg('--job-remove') || hasArg('--job-enable') || hasArg('--job-disable')) {
    try {
      if (handleJobCommands()) return;
    } catch (e) {
      console.error(`Job command failed: ${e.message}`);
      process.exitCode = 1;
      return;
    }
  }

  const cfg = loadConfig();
  await setupWizard(cfg);

  const mode = parseModeFromArgs() || await chooseModeWithArrows();
  if (mode === 'web') {
    await runWeb(cfg, { autoOpen: true });
    return;
  }
  if (mode === 'daemon') {
    await runDaemon();
    return;
  }
  await runCLI(cfg);
}

await main();
