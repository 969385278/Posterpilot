export type MemoryKey = 'style' | 'color' | 'title_font' | 'target_audience' | 'avoid_elements';
export type MemoryScope = 'all' | 'campus_lecture' | 'cultural_event' | 'club_recruitment';
export type MemorySuggestion = { key: MemoryKey; value: string; quote: string; scope: MemoryScope; kind: 'explicit' | 'temporary' | 'weak' };
export type MemoryEvent = MemorySuggestion & { id: string; source_id: string; revision: number; state: 'active' | 'recorded' | 'superseded' | 'retracted'; created_at: string };
export type UserProfile = { user_id: string; revision: number; scope: MemoryScope; preferences: Partial<Record<MemoryKey, MemoryEvent>> };
export type MemoryHistory = { events: MemoryEvent[]; next_before: number | null; audit: { action: string; reason: string; revision: number }[] };
const base = '/api/v1/datahub/users/local';

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(base + path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error?.message || '记忆请求失败，请刷新后重试。');
  }
  return response.json() as Promise<T>;
}

export const getProfile = (scope: MemoryScope = 'all') => request<UserProfile>(`/profile?scope=${scope}`);
export const getMemoryEvents = () => request<MemoryHistory>('/events');
export const saveMemorySource = (id: string, text: string) => request('/sources', { id, text });
export const extractMemory = (id: string, text: string) => request<{ suggestions: MemorySuggestion[] }>('/extract', { id, text });
export const recordMemory = (sourceId: string, suggestion: MemorySuggestion, revision: number) => request<MemoryEvent>('/events', {
  ...suggestion, source_id: sourceId, expected_revision: revision, confirmed: suggestion.kind === 'explicit',
});
export const retractMemory = (eventId: string, revision: number, reason: string) => request<UserProfile>(`/events/${eventId}/retract`, {
  expected_revision: revision, reason,
});
export const readMemorySource = (sourceId: string) => request<{ text: string }>(`/sources/${sourceId}`);
