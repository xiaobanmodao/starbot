import { Agent } from './agent.js';
import { loadBuiltInTools, loadCustomTools } from './tools/bootstrap.js';
import { listJobs, updateJob } from './daemon_store.js';
import { loadConversation, saveConversation } from './history/store.js';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nowMs() {
  return Date.now();
}

function nextDueAt(job) {
  const interval = Math.max(1, Number(job.interval_sec) || 1) * 1000;
  const last = job.last_run_at ? Date.parse(job.last_run_at) : NaN;
  if (!Number.isFinite(last)) return 0;
  return last + interval;
}

async function runJob(cfg, job, agents) {
  let agent = agents.get(job.id);
  if (!agent) {
    agent = new Agent(cfg);
    const record = loadConversation(job.conversation_id);
    if (record?.messages?.length) agent.loadMessages(record.messages, true);
    agents.set(job.id, agent);
  }

  const round = `自动任务：${job.name}\n目标：${job.objective}\n请继续执行下一轮并汇报关键结果。`;
  let gotError = '';
  let textOut = '';

  console.log(`[daemon] run job=${job.id} name=${job.name}`);
  for await (const ev of agent.run(round)) {
    if (ev.type === 'text') textOut += String(ev.content || '');
    if (ev.type === 'error') gotError = String(ev.message || 'unknown error');
    if (ev.type === 'confirm') {
      // Daemon mode runs unattended: dangerous actions are auto-approved.
      agent.confirm(true);
    }
  }

  try {
    saveConversation({
      id: job.conversation_id,
      title: `[daemon] ${job.name}`,
      messages: agent.getMessages(),
    });
  } catch {}

  updateJob(job.id, {
    last_run_at: new Date().toISOString(),
    last_status: gotError ? 'error' : 'ok',
    last_error: gotError || '',
  });

  if (gotError) {
    console.log(`[daemon] job=${job.id} status=error msg=${gotError}`);
  } else {
    const preview = textOut.replace(/\s+/g, ' ').trim().slice(0, 160);
    console.log(`[daemon] job=${job.id} status=ok output=${preview}`);
  }
}

export async function runDaemon(cfg) {
  await loadBuiltInTools();
  await loadCustomTools();

  const agents = new Map();
  const running = new Set();
  let stop = false;
  const shutdown = () => { stop = true; };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  console.log('[daemon] StarBot daemon started.');
  console.log('[daemon] Press Ctrl+C to stop.');

  while (!stop) {
    const jobs = listJobs().filter((job) => job.enabled);
    const now = nowMs();

    for (const job of jobs) {
      if (running.has(job.id)) continue;
      if (now < nextDueAt(job)) continue;

      running.add(job.id);
      runJob(cfg, job, agents)
        .catch((e) => {
          updateJob(job.id, {
            last_run_at: new Date().toISOString(),
            last_status: 'error',
            last_error: String(e?.message || e || 'unknown error'),
          });
        })
        .finally(() => running.delete(job.id));
    }

    await sleep(1000);
  }

  console.log('[daemon] Stopped.');
}
