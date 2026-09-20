import type { ToolTrace } from './client';

export type CaseNotes = {
  title: string; styles: string[]; problem: string; lesson: string;
  applicable_when: string; avoid_when: string;
  rights: 'unconfirmed' | 'own_or_authorized'; rights_note: string;
};
export type CaseFeedback = {
  verdict: 'unknown' | 'accepted' | 'rejected'; comment: string;
  source: 'not_collected' | 'explicit_user' | 'demo_fixture';
};
export type CaseStatus = 'candidate' | 'approved' | 'rejected' | 'withdrawn';
type EvidenceSnapshot = {
  brief: { title: string; poster_type: string; canvas: { width: number; height: number } };
  instruction: string; tool_traces: ToolTrace[];
  evaluation: { scores: { total: number; available_weight: number }; evaluator_version: string };
  layout: unknown; experience_references?: ExperienceReference[];
};
export type HubCase = {
  id: string; run_id: string; round_number: number; revision: number; status: CaseStatus;
  origin: 'runtime' | 'offline_demo'; notes: CaseNotes; feedback: CaseFeedback;
  image_hash: string; before_image_hash: string | null; evidence_hash: string;
  evidence: { before: EvidenceSnapshot | null; after: EvidenceSnapshot;
    comparison: { outcome: string; delta: number | null; reason: string | null } };
  audit: { revision: number; action: string; note: string; at: string;
    snapshot?: { notes: CaseNotes; feedback: CaseFeedback; status: CaseStatus } }[];
};
export type ExperienceReference = {
  case_id: string; revision: number; lesson: string; problem: string;
  applicable_when: string; avoid_when: string; origin: string; warning: string;
};
export type HubStats = {
  total: number; statuses: Record<CaseStatus, number>;
  feedback: Record<CaseFeedback['verdict'], number>; offline_demo: number; note: string;
};
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/datahub${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.error?.message ?? (typeof error?.detail === 'string' ? error.detail : `请求失败（${response.status}）`));
  }
  return response.json() as Promise<T>;
}
const json = (method: string, body: unknown) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
export const listHubCases = () => request<HubCase[]>('/cases');
export const hubStats = () => request<HubStats>('/stats');
export const captureRun = (id: string) => request<HubCase[]>(`/capture/${encodeURIComponent(id)}`, { method: 'POST' });
export const caseQuality = (id: string) => request<{ issues: string[]; revision: number }>(`/cases/${id}/quality`);
export const editCase = (item: HubCase, notes: CaseNotes, feedback: CaseFeedback) =>
  request<HubCase>(`/cases/${item.id}`, json('PUT', { expected_revision: item.revision, notes, feedback }));
export const reviewCase = (item: HubCase, action: 'approve' | 'reject' | 'withdraw', note: string) =>
  request<HubCase>(`/cases/${item.id}/review`, json('POST', { expected_revision: item.revision, action, note }));
export const retrieveExperiences = (query: string, poster_type: string, include_demo: boolean, exclude_run_id?: string) =>
  request<{ matches: ExperienceReference[]; method: string; note: string }>('/retrieve', json('POST', {
    query, poster_type, include_demo, exclude_run_id: exclude_run_id || null,
  }));
export const hubImage = (id: string, before = false) => `/api/v1/datahub/cases/${id}/image?before=${before}`;
