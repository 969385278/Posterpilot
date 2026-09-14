// UI test fixtures only; never added to the real case catalog.
import type { HumanCheckpoint } from '../../api/client';
import { emptyControls, type LayoutCandidate, type PosterCase, type PosterAnalysis } from '../../api/design';

export const analysisFixture: PosterAnalysis = {
  version: 'poster_initial.png', palette: ['#102030'], features: [],
  text_facts: [{ element_id: 'title', content: '社团招新', requested_font_size: 72, actual_font_size: 64, font_name: '测试字体', color: '#ffffff', line_count: 1, fits_box: true }],
  visual_summary: '', warnings: [], readability_checks: [],
};
export const checkpointFixture: HumanCheckpoint = {
  round_number: 0, score: 75, primary_issues: [], suggestion: '选择你希望修改的特点', citations: [], tool_traces: [], rounds: [],
  poster_artifact: 'poster_initial.png', attention_artifact: null, analysis: analysisFixture, initial_analysis: analysisFixture,
  controls: emptyControls(),
  layout: { canvas: { width: 1080, height: 1440 }, elements: [
    { id: 'title', role: 'title', content: '社团招新', box: { x: 0.1, y: 0.1, width: 0.8, height: 0.1 } },
    { id: 'event_info', role: 'event_info', content: '周五 活动中心', box: { x: 0.1, y: 0.8, width: 0.8, height: 0.1 } },
  ] },
};
export const candidateFixture: LayoutCandidate = {
  id: 'round-0-bottom', round_number: 0, label: '底部标题', poster_artifact: 'candidates/round_0_bottom.png',
  layout: checkpointFixture.layout!, analysis: analysisFixture,
  attention: { availability: 'unavailable', predicted_path: [] }, checks: [], subject_overlap: null,
  rank_score: 70, attention_used_for_ranking: false, is_current: false, selectable: true, notes: ['主体保护信息不可用'],
};
export const caseFixture: PosterCase = {
  id: 'fixture-case', title: '测试蓝橙海报', original_title: 'FIXTURE', image_asset: 'fixture.jpg', styles: ['蓝橙'], scenarios: ['社团'],
  features: { palette: '蓝橙配色', typography: '装饰字形但字体未知', composition: '主体居中', hierarchy: '标题优先' },
  palette: ['#102030'], suggested_priority: ['title'], cautions: ['测试数据'],
  source: { creator: 'Fixture', institution: 'Fixture', source_url: 'https://example.org/fixture', image_url: 'https://example.org/image.jpg', rights: 'test', rights_url: 'https://example.org/rights', retrieved_at: '2026-09-11', image_sha256: '0'.repeat(64) },
  analysis_basis: 'assistant_visual_review', user_acceptance: 'pending',
};
