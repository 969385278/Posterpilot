import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DataHubPage } from './DataHubPage';
import * as api from '../api/datahub';
import type { HubCase } from '../api/datahub';

vi.mock('../api/datahub', () => ({
  listHubCases: vi.fn(), hubStats: vi.fn(), caseQuality: vi.fn(), editCase: vi.fn(),
  reviewCase: vi.fn(), captureRun: vi.fn(), retrieveExperiences: vi.fn(),
  hubImage: (id: string) => `/test/${id}.png`,
}));
const item = {
  id: 'case-1', run_id: 'run-1', round_number: 1, revision: 1, status: 'candidate', origin: 'runtime',
  image_hash: 'a', before_image_hash: 'b', evidence_hash: 'c',
  notes: { title: '音乐节案例', styles: [], problem: '标题不醒目', lesson: '检查对比度', applicable_when: '短标题', avoid_when: '长标题', rights: 'own_or_authorized', rights_note: '自有' },
  feedback: { verdict: 'unknown', comment: '', source: 'not_collected' }, audit: [],
  evidence: { before: null, after: { instruction: '标题不醒目', tool_traces: [], layout: {}, brief: { title: '音乐节', poster_type: 'cultural_event', canvas: { width: 1080, height: 1440 } }, evaluation: { scores: { total: 80, available_weight: 40 }, evaluator_version: 'test' } }, comparison: { outcome: 'not_comparable', delta: null, reason: '评测信号不同' } },
} satisfies HubCase;

describe('PosterHub', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.listHubCases).mockResolvedValue([item]);
    vi.mocked(api.hubStats).mockResolvedValue({ total: 1, statuses: { candidate: 1, approved: 0, rejected: 0, withdrawn: 0 }, feedback: { unknown: 1, accepted: 0, rejected: 0 }, offline_demo: 0, note: '' });
    vi.mocked(api.caseQuality).mockResolvedValue({ issues: [], revision: 1 });
  });
  it('shows an honest empty state', async () => {
    vi.mocked(api.listHubCases).mockResolvedValue([]);
    render(<DataHubPage />);
    expect(await screen.findByText('这里还没有匹配的案例')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '去创建一张海报' })).toHaveAttribute('href', '#workspace');
  });
  it('keeps unknown feedback and incomparable scores separate', async () => {
    render(<DataHubPage />);
    fireEvent.click(await screen.findByRole('button', { name: '查看 音乐节案例' }));
    expect(screen.getByLabelText('是否接受')).toHaveValue('unknown');
    expect(screen.getByText('不可直接比较分数：评测信号不同')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '批准作为参考' })).toBeDisabled();
  });
  it('requires saving edited notes before review and passes revision', async () => {
    vi.mocked(api.editCase).mockImplementation(async (_old, notes, feedback) => ({ ...item, notes, feedback, revision: 2 }));
    render(<DataHubPage />);
    fireEvent.click(await screen.findByRole('button', { name: '查看 音乐节案例' }));
    await screen.findByText('基础资料检查通过。请继续人工检查经验是否可信、条件是否清楚。');
    fireEvent.change(screen.getByLabelText('审核说明'), { target: { value: '审核通过' } });
    expect(screen.getByRole('button', { name: '批准作为参考' })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('复用建议'), { target: { value: '修改建议' } });
    expect(screen.getByRole('button', { name: '批准作为参考' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '保存整理信息，转为待审核' }));
    await waitFor(() => expect(api.editCase).toHaveBeenCalledWith(item, expect.objectContaining({ lesson: '修改建议' }), item.feedback));
  });
  it('reports a conflict without claiming success', async () => {
    vi.mocked(api.reviewCase).mockRejectedValue(new Error('案例已被修改，请刷新后重新提交。'));
    render(<DataHubPage />);
    fireEvent.click(await screen.findByRole('button', { name: '查看 音乐节案例' }));
    await screen.findByText('基础资料检查通过。请继续人工检查经验是否可信、条件是否清楚。');
    fireEvent.change(screen.getByLabelText('审核说明'), { target: { value: '审核通过' } });
    fireEvent.click(screen.getByRole('button', { name: '批准作为参考' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('案例已被修改');
    expect(api.reviewCase).toHaveBeenCalledWith(item, 'approve', '审核通过');
  });
  it('retrieval experiment excludes the current run and labels its limits', async () => {
    vi.mocked(api.retrieveExperiences).mockResolvedValue({ matches: [], method: 'reviewed_text_bigrams', note: '' });
    render(<DataHubPage initialRunId="run-1" />);
    fireEvent.click(screen.getByRole('button', { name: '检索验证' }));
    fireEvent.click(screen.getByRole('button', { name: '运行检索对照' }));
    expect(await screen.findByText('没有匹配参考，Agent 应继续原流程，不编造历史经验。')).toBeInTheDocument();
    expect(api.retrieveExperiences).toHaveBeenCalledWith('标题不醒目', 'cultural_event', false, 'run-1');
    expect(screen.getByText(/这是输入参考对照，不是生成质量实验/)).toBeInTheDocument();
  });
  it('shows fetch errors and supports retry', async () => {
    vi.mocked(api.listHubCases).mockRejectedValueOnce(new Error('服务不可用'));
    render(<DataHubPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('服务不可用');
    fireEvent.click(screen.getByRole('button', { name: '刷新' }));
    expect(await screen.findByRole('button', { name: '查看 音乐节案例' })).toBeInTheDocument();
  });
  it('preserves separators while typing tags and saves parsed values', async () => {
    vi.mocked(api.editCase).mockImplementation(async (_old, notes, feedback) => ({ ...item, notes, feedback, revision: 2 }));
    render(<DataHubPage />);
    fireEvent.click(await screen.findByRole('button', { name: '查看 音乐节案例' }));
    const tags = screen.getByLabelText('风格标签（逗号分隔）');
    fireEvent.change(tags, { target: { value: '复古，' } });
    expect(tags).toHaveValue('复古，');
    fireEvent.change(tags, { target: { value: '复古，低饱和' } });
    fireEvent.click(screen.getByRole('button', { name: '保存整理信息，转为待审核' }));
    await waitFor(() => expect(api.editCase).toHaveBeenCalledWith(item, expect.objectContaining({ styles: ['复古', '低饱和'] }), item.feedback));
  });
  it('shows the prior curated version alongside audit notes', async () => {
    vi.mocked(api.listHubCases).mockResolvedValue([{ ...item, audit: [{
      revision: 2, action: 'approve', note: '已核对', at: '2026-09-20T00:00:00Z',
      snapshot: { notes: { ...item.notes, lesson: '历史建议不能丢失' }, feedback: item.feedback, status: 'approved' },
    }] }]);
    render(<DataHubPage />);
    fireEvent.click(await screen.findByRole('button', { name: '查看 音乐节案例' }));
    expect(screen.getByText(/历史建议不能丢失/)).toBeInTheDocument();
  });
});
