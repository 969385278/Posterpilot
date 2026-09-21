import type { RunRecord } from './client';

export type DesignAnswer = {
  id: string; conversation_id: string; question: string; answer: string;
  run_id: string | null; round_number: number | null; degraded: boolean;
  citations: { id: string; title: string; source: string; excerpt: string }[];
  trace: { tool: string; summary: string; success: boolean }[];
  proposal: { scope: string; instruction: string } | null;
};

async function checked<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error?.message || (typeof body.detail === 'string' ? body.detail : '设计助手请求失败，请稍后重试。'));
  }
  return response.json() as Promise<T>;
}

export async function askDesign(question: string, runId?: string, conversationId?: string): Promise<DesignAnswer> {
  return checked(await fetch('/api/v1/assistant/questions', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, run_id: runId, conversation_id: conversationId }),
  }));
}

export async function confirmDesign(answerId: string): Promise<RunRecord> {
  return checked(await fetch(`/api/v1/assistant/answers/${encodeURIComponent(answerId)}/confirm`, { method: 'POST' }));
}
