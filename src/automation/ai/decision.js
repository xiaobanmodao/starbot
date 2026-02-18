import OpenAI from 'openai';
import { GENERIC_AI_DECISION_PROMPT } from './prompt.js';

function fallbackDecision(input, reasonCode = 'ai_unavailable') {
  return {
    task_id: String(input?.task_id || ''),
    event_type: String(input?.event_type || 'ambiguous_condition'),
    analysis: {
      classification: 'unknown',
      confidence: 0,
      uncertainty_level: 'high',
      recommended_action: 'escalate',
      reason_codes: [reasonCode],
    },
  };
}

function isDecisionShape(x) {
  return x
    && typeof x === 'object'
    && typeof x.task_id === 'string'
    && typeof x.event_type === 'string'
    && x.analysis
    && typeof x.analysis === 'object'
    && typeof x.analysis.classification === 'string'
    && typeof x.analysis.confidence === 'number'
    && typeof x.analysis.uncertainty_level === 'string'
    && typeof x.analysis.recommended_action === 'string'
    && Array.isArray(x.analysis.reason_codes);
}

export function shouldTriggerAIDecision(rule = {}, event = {}) {
  if (!rule || !rule.enabled) return false;
  const condition = String(rule.condition || '').trim().toLowerCase();
  if (!condition || condition === 'none') return false;
  if (condition === 'multiple_metrics_conflict') return Boolean(event?.context?.metrics_conflict);
  if (condition === 'unknown_pattern') return Boolean(event?.context?.unknown_pattern);
  if (condition === 'action_error_repeated') {
    const streak = Number(event?.context?.error_streak || 0);
    const threshold = Math.max(1, Number(rule.threshold || 2));
    return streak >= threshold;
  }
  return false;
}

export async function runAIDecision(cfg, structuredInput) {
  const key = String(cfg?.api_key || '').trim();
  if (!key) return fallbackDecision(structuredInput, 'missing_api_key');

  try {
    const client = new OpenAI({
      apiKey: key,
      baseURL: cfg?.base_url,
    });
    const response = await client.chat.completions.create({
      model: cfg?.model || 'gpt-4o',
      temperature: 0,
      max_tokens: 400,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: GENERIC_AI_DECISION_PROMPT },
        { role: 'user', content: JSON.stringify(structuredInput) },
      ],
    });
    const text = response?.choices?.[0]?.message?.content || '';
    const parsed = JSON.parse(text);
    if (!isDecisionShape(parsed)) return fallbackDecision(structuredInput, 'invalid_ai_output');
    return parsed;
  } catch {
    return fallbackDecision(structuredInput, 'ai_call_failed');
  }
}
