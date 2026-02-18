import { listPendingByConversation, markReported } from '../store/results.js';

export function collectConversationSummary(conversationId) {
  const pending = listPendingByConversation(conversationId);
  if (!pending.length) return null;

  const byTask = new Map();
  for (const item of pending) {
    if (!byTask.has(item.task_id)) byTask.set(item.task_id, []);
    byTask.get(item.task_id).push(item);
  }

  const lines = [];
  lines.push('这是你离线期间后台自动化任务的汇总：');
  for (const [taskId, items] of byTask.entries()) {
    const ok = items.filter((it) => it.status === 'ok').length;
    const err = items.filter((it) => it.status !== 'ok').length;
    lines.push(`- 任务 ${taskId}：新增 ${items.length} 条事件（成功 ${ok}，失败 ${err}）。`);
  }

  const first = pending[0];
  const last = pending[pending.length - 1];
  lines.push(`时间范围：${first.timestamp} 至 ${last.timestamp}。`);
  lines.push('如需明细，我可以继续列出每条结构化事件。');

  return {
    text: lines.join('\n'),
    resultIds: pending.map((it) => it.id),
  };
}

export function markSummaryReported(resultIds = []) {
  return markReported(resultIds);
}
