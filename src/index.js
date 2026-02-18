import readline from 'readline/promises';
import * as readlineCore from 'readline';
import chalk from 'chalk';
import { stdin as input, stdout as output, argv } from 'process';
import { loadConfig, setupWizard } from './config.js';
import { runCLI } from './cli.js';
import { runWeb } from './web/server.js';

function parseModeFromArgs() {
  if (argv.includes('--web')) return 'web';
  if (argv.includes('--cli')) return 'cli';
  return null;
}

async function chooseModeWithArrows() {
  const rl = readline.createInterface({ input, output });
  readlineCore.emitKeypressEvents(input, rl);

  const options = [
    { value: 'cli', label: 'CLI' },
    { value: 'web', label: 'Web (auto open browser)' },
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

const cfg = loadConfig();
await setupWizard(cfg);

const mode = parseModeFromArgs() || await chooseModeWithArrows();
if (mode === 'web') {
  await runWeb(cfg, { autoOpen: true });
} else {
  await runCLI(cfg);
}
