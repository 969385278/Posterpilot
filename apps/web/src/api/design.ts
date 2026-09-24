export type TraitKey = 'background_contrast' | 'background_saturation' | 'title_emphasis';
export type TraitDirection = 'preserve' | 'strengthen' | 'weaken';
export type PriorityRole = 'title' | 'subtitle' | 'main_visual' | 'event_info' | 'organizer';
export type ReferenceAspect = 'palette' | 'typography' | 'composition' | 'hierarchy';
export type LockProperty = 'content' | 'position' | 'typography';
export type ReferenceSelection = { case_id: string; aspects: ReferenceAspect[] };
export type ElementGoal =
  | { kind: 'opacity'; element_id: string; opacity: number }
  | { kind: 'alignment'; element_id: string; reference_id: string; edge: 'left' | 'center' | 'right' };
export type DesignControls = {
  adjustments: { trait: TraitKey; direction: TraitDirection; strength: number }[];
  locks: { element_id: string; properties: LockProperty[] }[];
  attention_priority: PriorityRole[];
  selected_candidate_id?: string | null;
  element_goals?: ElementGoal[];
  fact_edits?: { field: 'title' | 'subtitle' | 'event_time' | 'location' | 'organizer'; element_id: string; before: string; after: string }[];
};
export type PosterLayout = {
  canvas: { width: number; height: number };
  elements: { id: string; role: string; content?: string | null; box: { x: number; y: number; width: number; height: number }; font_size?: number; color?: string }[];
};
export type VerificationCheck = { key: string; label: string; status: 'passed' | 'failed' | 'unavailable'; detail: string; before?: number | null; after?: number | null };
export type GoalVerification = { checks: VerificationCheck[]; outcome: 'met' | 'not_met' | 'unverified' | 'no_change_requested'; summary: string };
export type PosterAnalysis = {
  version: string;
  palette: string[];
  features: { key: string; label: string; value: number | null; unit: string; basis: 'image_measurement' | 'render_metadata' | 'model_judgment'; explanation: string; controllable: boolean }[];
  text_facts: { element_id: string; content: string; requested_font_size: number; actual_font_size: number; font_name: string; color: string; line_count: number; fits_box: boolean }[];
  visual_summary: string;
  warnings: string[];
  readability_checks: VerificationCheck[];
};
export type LayoutCandidate = {
  id: string; round_number: number; label: string; poster_artifact: string;
  layout: PosterLayout; analysis: PosterAnalysis;
  attention: { availability: string; model?: string | null; predicted_path: string[]; heatmap_artifact?: string | null };
  checks: VerificationCheck[]; subject_overlap: number | null; rank_score: number;
  attention_used_for_ranking: boolean; is_current: boolean; selectable: boolean; notes: string[];
};
export type PosterCase = {
  id: string; title: string; original_title: string; image_asset: string;
  styles: string[]; scenarios: string[]; features: Record<ReferenceAspect, string>; palette: string[];
  suggested_priority: PriorityRole[]; cautions: string[];
  source: { creator: string; institution: string; source_url: string; image_url: string; rights: string; rights_url: string; retrieved_at: string; image_sha256: string };
  analysis_basis: string; user_acceptance: string;
};

export const roleLabels: Record<string, string> = { title: '标题', subtitle: '副标题', main_visual: '主视觉', event_info: '活动信息', organizer: '主办方' };
export const aspectLabels: Record<ReferenceAspect, string> = { palette: '配色', typography: '字体气质', composition: '构图', hierarchy: '信息层级' };
export const traitLabels: Record<TraitKey, string> = { background_contrast: '背景明暗反差', background_saturation: '背景饱和度', title_emphasis: '标题字号层级' };
export const emptyControls = (): DesignControls => ({ adjustments: [], locks: [], attention_priority: [], selected_candidate_id: null });

export function caseImageUrl(caseId: string): string { return `/api/v1/poster-cases/${encodeURIComponent(caseId)}/image`; }
export async function listPosterCases(signal?: AbortSignal): Promise<PosterCase[]> {
  const response = await fetch('/api/v1/poster-cases', { signal });
  if (!response.ok) throw new Error('案例库暂时无法读取，可重试或不选案例直接生成。');
  return await response.json() as PosterCase[];
}

// A dimension has exactly one source. Selecting a new source moves that
// dimension, while preserving other selections. At most three source posters.
export function selectReferenceAspect(current: ReferenceSelection[], caseId: string, aspect: ReferenceAspect, checked: boolean): ReferenceSelection[] {
  const next = current.map(item => ({ ...item, aspects: item.aspects.filter(value => value !== aspect || (!checked && item.case_id !== caseId)) })).filter(item => item.aspects.length);
  if (!checked) return next;
  const existing = next.find(item => item.case_id === caseId);
  if (existing) existing.aspects.push(aspect);
  else next.push({ case_id: caseId, aspects: [aspect] });
  if (next.length > 3) throw new Error('最多参考三张海报，请先取消一张的选择。');
  return next;
}
