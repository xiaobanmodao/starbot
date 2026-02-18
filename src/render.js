import chalk from 'chalk';

const THEMES = {
  ocean: {
    cyan: chalk.cyanBright,
    blue: chalk.blueBright,
    gray: chalk.gray,
    white: chalk.whiteBright,
    green: chalk.greenBright,
    menuActive: chalk.whiteBright.bgBlue,
    menuInactive: chalk.gray,
  },
  glacier: {
    cyan: chalk.cyan,
    blue: chalk.blue,
    gray: chalk.gray,
    white: chalk.white,
    green: chalk.green,
    menuActive: chalk.black.bgCyanBright,
    menuInactive: chalk.gray,
  },
  aurora: {
    cyan: chalk.cyanBright,
    blue: chalk.hex('#4ea8ff'),
    gray: chalk.hex('#8b96a5'),
    white: chalk.hex('#f2f5f9'),
    green: chalk.hex('#4dd78a'),
    menuActive: chalk.black.bgHex('#4dd78a'),
    menuInactive: chalk.hex('#8b96a5'),
  },
  slate: {
    cyan: chalk.hex('#74c0fc'),
    blue: chalk.hex('#5c7cfa'),
    gray: chalk.hex('#868e96'),
    white: chalk.hex('#f1f3f5'),
    green: chalk.hex('#69db7c'),
    menuActive: chalk.whiteBright.bgHex('#364fc7'),
    menuInactive: chalk.hex('#868e96'),
  },
};

let themeName = 'ocean';
let theme = THEMES[themeName];

export function setTheme(name) {
  const key = String(name || '').toLowerCase();
  if (!THEMES[key]) return false;
  themeName = key;
  theme = THEMES[key];
  return true;
}

export function getThemeName() {
  return themeName;
}

export function getThemeNames() {
  return Object.keys(THEMES);
}

export function banner() {
  const art = [
    '  ███████ ████████  █████  ██████  ██████   ██████  ████████',
    '  ██         ██    ██   ██ ██   ██ ██   ██ ██    ██    ██',
    '  ███████    ██    ███████ ██████  ██████  ██    ██    ██',
    '       ██    ██    ██   ██ ██   ██ ██   ██ ██    ██    ██',
    '  ███████    ██    ██   ██ ██   ██ ██████   ██████     ██',
  ].join('\n');
  return [
    theme.cyan(art),
    theme.gray(`  local coding agent · minimal interface · theme: ${themeName}`),
  ].join('\n');
}

export function toolCallHeader(name) {
  return theme.blue(`\n• tool  ${String(name || '')}`);
}

export function toolArgs(args) {
  return theme.gray(String(args || ''));
}

export function toolResult(result) {
  const text = String(result || '');
  const display = text.length > 2000 ? `${text.slice(0, 2000)}...` : text;
  return theme.white(display);
}

export function errorText(msg) {
  return theme.blue(String(msg || ''));
}

export function dimText(msg) {
  return theme.gray(String(msg || ''));
}

export function accentText(msg) {
  return theme.cyan(String(msg || ''));
}

export function inputPrompt() {
  return theme.cyan('› ');
}

export function createSpinner(text = 'thinking') {
  if (process.env.STARBOT_SPINNER === '0') {
    return { start() {}, stop() {}, setRightText() {} };
  }

  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
  let index = 0;
  let timer = null;
  let rightText = '';

  const renderFrame = () => {
    const frame = theme.cyan(frames[index % frames.length]);
    const left = `${frame} ${theme.gray(text)}`;
    const right = rightText ? theme.gray(rightText) : '';
    const cols = process.stderr.columns || 100;
    const pad = Math.max(2, cols - stripAnsi(left).length - stripAnsi(right).length);
    process.stderr.write(`\r${left}${' '.repeat(pad)}${right}`);
    index++;
  };

  return {
    start() {
      if (timer) return;
      timer = setInterval(renderFrame, 90);
      renderFrame();
    },
    stop() {
      if (!timer) return;
      clearInterval(timer);
      timer = null;
      process.stderr.write('\r\x1b[K');
    },
    setRightText(value = '') {
      rightText = String(value || '');
      if (timer) renderFrame();
    },
  };
}

export function streamWrite(text) {
  process.stdout.write(String(text || ''));
}

export function tokenUsageLine(cumulative = {}) {
  const total = Number(cumulative?.total_tokens || 0).toLocaleString('en-US');
  return theme.green(`(${total} tokens)`);
}

export function menuActive(text) {
  return theme.menuActive(String(text || ''));
}

export function menuInactive(text) {
  return theme.menuInactive(String(text || ''));
}

function stripAnsi(text) {
  return String(text || '').replace(/\x1B\[[0-9;]*m/g, '');
}
