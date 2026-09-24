import type { DesignControls, GoalVerification, LayoutCandidate, PosterAnalysis, PosterLayout, PriorityRole, ReferenceSelection } from './design';

export type PosterBriefInput = {
  poster_type: 'campus_lecture' | 'cultural_event' | 'club_recruitment';
  topic: string;
  target_audience: string;
  title: string;
  title_font?: 'auto' | 'standard' | 'mashanzheng' | 'longcang' | 'zhimangxing' | 'zcoolkuaile' | 'zcoolqingkehuangyou' | 'zcoolxiaowei';
  subtitle?: string;
  event_time: string;
  location: string;
  organizer: string;
  style_preferences: string[];
  color_preferences: string[];
  visual_elements: string[];
  avoid_elements: string[];
  notes: string;
  references?: ReferenceSelection[];
  attention_priority?: PriorityRole[];
  attention_layout?: boolean;
  use_case_memory?: boolean;
  use_user_memory?: boolean;
  user_id?: string;
};

export type RunRecord = {
  id: string;
  status: 'queued' | 'running' | 'waiting_for_human' | 'completed' | 'failed';
  current_node: string | null;
  error_message: string | null;
  artifacts: ArtifactReference[];
};

export type ArtifactReference = {
  name: string;
  relative_path: string;
  media_type: string;
};

export type RunEvent = {
  id?: string;
  type: string;
  node: string | null;
  message: string;
  payload?: Record<string, unknown>;
  created_at?: string;
};

export type ReactToolName =
  | 'search_design_knowledge'
  | 'search_poster_cases'
  | 'modify_typography'
  | 'modify_layout'
  | 'modify_visual'
  | 'adjust_background'
  | 'set_text_opacity'
  | 'align_text_group'
  | 'finish_round';

export type ToolTrace = {
  round_number: number;
  step: number;
  decision_summary: string;
  tool_name: ReactToolName;
  tool_args: Record<string, unknown>;
  observation: string;
  success: boolean;
  knowledge_card_ids: string[];
};

export type RoundSnapshot = {
  round_number: number;
  poster_artifact: string;
  attention_artifact: string | null;
  score: number;
  score_delta: number | null;
  comparison_reason?: string | null;
  evaluation: Record<string, unknown>;
  tool_traces: ToolTrace[];
  analysis?: PosterAnalysis | null;
  controls?: DesignControls;
  goal_verification?: GoalVerification | null;
  background_treatment?: { contrast: number; saturation: number };
};

export type HumanCheckpoint = {
  initial_attention_artifact?: string | null;
  round_number: number;
  score: number;
  evaluation_notes?: string[];
  primary_issues: string[];
  suggestion: string;
  citations: {
    card_id: string;
    title: string;
    source_id: string;
    source_pages: number[];
  }[];
  tool_traces: ToolTrace[];
  poster_artifact: string | null;
  attention_artifact: string | null;
  rounds: RoundSnapshot[];
  layout?: PosterLayout | null;
  analysis?: PosterAnalysis | null;
  initial_analysis?: PosterAnalysis | null;
  controls?: DesignControls;
  goal_verification?: GoalVerification | null;
  layout_candidates?: LayoutCandidate[];
};

export type HumanDecision =
  | { action: 'approve'; controls?: DesignControls }
  | { action: 'instruct'; instruction?: string; controls?: DesignControls }
  | { action: 'finish' };

export type RunResult = {
  poster_initial_path: string | null;
  poster_optimized_path: string | null;
  score_delta: number | null;
  comparison_reason?: string | null;
  outcome: 'improved' | 'unchanged' | 'declined' | 'not_comparable';
  evaluation_initial: EvaluationResult;
  evaluation_optimized: EvaluationResult;
  rounds?: RoundSnapshot[];
  tool_traces?: ToolTrace[];
  analysis_initial?: PosterAnalysis | null;
  analysis_current?: PosterAnalysis | null;
  goal_verification?: GoalVerification | null;
};

export type EvaluationResult = {
  scores: { total: number; available_weight: number };
  attention: { availability: string; heatmap_artifact: string | null };
};

export async function createRun(brief: PosterBriefInput): Promise<RunRecord> {
  const response = await fetch('/api/v1/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(brief),
  });
  if (!response.ok) {
    throw new Error(await responseMessage(response, '创建任务失败，请检查后端服务是否已启动。'));
  }
  return (await response.json()) as RunRecord;
}

export async function getRun(runId: string): Promise<RunRecord> {
  const response = await fetch(`/api/v1/runs/${runId}`);
  if (!response.ok) {
    throw new Error('读取任务状态失败。');
  }
  return (await response.json()) as RunRecord;
}

export async function listRuns(): Promise<RunRecord[]> {
  const response = await fetch('/api/v1/runs');
  if (!response.ok) {
    throw new Error('读取任务历史失败。');
  }
  return (await response.json()) as RunRecord[];
}

export async function getRunResult(runId: string): Promise<RunResult> {
  const response = await fetch(artifactUrl(runId, 'result.json'));
  if (!response.ok) {
    throw new Error('读取任务结果失败。');
  }
  return (await response.json()) as RunResult;
}

export async function getPendingHumanInput(runId: string): Promise<HumanCheckpoint> {
  const response = await fetch(`/api/v1/runs/${runId}/pending`);
  if (!response.ok) {
    throw new Error('读取 Agent 待确认信息失败。');
  }
  return (await response.json()) as HumanCheckpoint;
}

export async function submitHumanDecision(
  runId: string,
  decision: HumanDecision,
  expectedRoundNumber: number,
): Promise<RunRecord> {
  const response = await fetch(`/api/v1/runs/${runId}/decisions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...decision, expected_round_number: expectedRoundNumber }),
  });
  if (!response.ok) {
    throw new Error(await responseMessage(response, '提交人工决策失败，请刷新任务状态后重试。'));
  }
  return (await response.json()) as RunRecord;
}

export function artifactUrl(runId: string, name: string): string {
  return `/api/v1/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(name)}`;
}

async function responseMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.error?.message === 'string') return body.error.message;
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('；') || fallback;
  } catch { /* Missing or non-JSON error body. */ }
  return fallback;
}

export function subscribeRunEvents(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError: () => void,
): () => void {
  const source = new EventSource(`/api/v1/runs/${runId}/events`);
  const types = [
    'run_created',
    'node_started',
    'node_completed',
    'human_input_required',
    'human_input_received',
    'agent_decision',
    'tool_started',
    'tool_completed',
    'round_completed',
    'experience_captured',
    'experience_capture_pending',
    'run_completed',
    'run_failed',
  ];
  for (const type of types) {
    source.addEventListener(type, (message) => {
      onEvent(JSON.parse((message as MessageEvent<string>).data) as RunEvent);
    });
  }
  // Historical pauses do not terminate a replay. Only the server's explicit end
  // marker closes it; transient failures retain native Last-Event-ID reconnects.
  source.addEventListener('stream_end', () => source.close());
  source.onerror = () => { onError(); };
  return () => source.close();
}
