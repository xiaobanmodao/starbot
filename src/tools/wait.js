import { tool } from './registry.js';

tool('wait_seconds', 'Pause execution for a number of seconds. Useful for continuous monitoring loops.', {
  properties: {
    seconds: { type: 'number', description: 'Seconds to wait (0-3600)' },
  },
  required: ['seconds'],
}, false, async ({ seconds }) => {
  const raw = Number(seconds);
  if (!Number.isFinite(raw)) return '[error] seconds must be a number';
  const s = Math.max(0, Math.min(3600, Math.trunc(raw)));
  await new Promise((resolve) => setTimeout(resolve, s * 1000));
  return `Waited ${s} second(s).`;
});
