export type AppRoute = { page: 'home' | 'workspace' | 'history' | 'datahub'; runId?: string };

export function readRoute(): AppRoute {
  const hash = window.location.hash;
  const hubMatch = /^#datahub(?:\/([0-9a-f-]{36}))?$/i.exec(hash);
  if (hubMatch) return { page: 'datahub', runId: hubMatch[1] };
  if (hash === '#history') return { page: 'history' };
  const match = /^#runs\/([0-9a-f-]{36})$/i.exec(hash);
  if (match) return { page: 'workspace', runId: match[1] };
  if (hash === '#workspace') return { page: 'workspace' };
  return { page: 'home' };
}

export function openRun(runId: string) {
  window.location.hash = `runs/${encodeURIComponent(runId)}`;
}
