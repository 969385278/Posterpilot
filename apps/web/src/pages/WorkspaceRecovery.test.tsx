import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../api/client';
import { WorkspacePage } from './WorkspacePage';

vi.mock('../api/client', async (original) => ({
  ...await original<typeof api>(),
  getRun: vi.fn(), getPendingHumanInput: vi.fn(), getRunResult: vi.fn(),
  submitHumanDecision: vi.fn(),
  subscribeRunEvents: vi.fn(() => vi.fn()),
}));
const id = '12345678-aaaa-bbbb-cccc-dddddddddddd';
const record: api.RunRecord = { id, status: 'waiting_for_human', current_node: 'human_review', error_message: null, artifacts: [] };
const checkpoint: api.HumanCheckpoint = {
  round_number: 0, score: 75, primary_issues: ['标题层级需要增强'], suggestion: '请确认初版',
  citations: [], tool_traces: [], poster_artifact: 'poster_initial.png', attention_artifact: null, rounds: [],
};

describe('workspace task recovery', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads an existing paused run and restores its human controls', async () => {
    vi.mocked(api.getRun).mockResolvedValue(record);
    vi.mocked(api.getPendingHumanInput).mockResolvedValue(checkpoint);
    render(<WorkspacePage initialRunId={id} onOpenHistory={() => undefined} />);
    expect(await screen.findByRole('button', { name: '按建议优化' })).toBeInTheDocument();
    expect(screen.getByText('请确认初版')).toBeInTheDocument();
    expect(api.getRun).toHaveBeenCalledWith(id);
    expect(api.subscribeRunEvents).toHaveBeenCalledTimes(1);
  });

  it('shows recovery failure and allows retry rather than a blank new form', async () => {
    vi.mocked(api.getRun).mockRejectedValueOnce(new Error('任务不存在')).mockResolvedValue(record);
    vi.mocked(api.getPendingHumanInput).mockResolvedValue(checkpoint);
    render(<WorkspacePage initialRunId={id} onOpenHistory={() => undefined} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('任务不存在');
    expect(screen.queryByRole('button', { name: '开始生成' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重新读取任务' }));
    expect(await screen.findByRole('button', { name: '按建议优化' })).toBeInTheDocument();
  });

  it('keeps the reviewed poster while optimizing and displays missing evaluation signals', async () => {
    vi.mocked(api.getRun).mockResolvedValueOnce(record).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getPendingHumanInput).mockResolvedValue({ ...checkpoint,
      evaluation_notes: ['视觉评测不可用，当前分数未包含视觉模型判断。'],
    });
    vi.mocked(api.submitHumanDecision).mockResolvedValue({ ...record, status: 'running' });
    render(<WorkspacePage initialRunId={id} onOpenHistory={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', {name: '按建议优化'}));
    await waitFor(() => expect(screen.queryByRole('button', {name: '按建议优化'})).not.toBeInTheDocument());
    expect(screen.getByRole('img', {name: '初版海报'})).toBeInTheDocument();
    expect(screen.queryByRole('img', {name: '生成结果出现前的海报示例'})).not.toBeInTheDocument();
    expect(screen.getByText('视觉评测不可用，当前分数未包含视觉模型判断。')).toBeInTheDocument();
  });

  it('submits the reviewed round and preserves the instruction if rejected', async () => {
    vi.mocked(api.getRun).mockResolvedValue(record);
    vi.mocked(api.getPendingHumanInput).mockResolvedValue({ ...checkpoint, round_number: 1 });
    vi.mocked(api.submitHumanDecision).mockRejectedValue(new Error('请刷新任务状态后重试。'));
    render(<WorkspacePage initialRunId={id} onOpenHistory={() => undefined} />);
    const input = await screen.findByLabelText('告诉 Agent 这一轮怎么改');
    fireEvent.change(input, { target: { value: '让活动时间更醒目' } });
    fireEvent.click(screen.getByRole('button', { name: '提交修改要求' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('请刷新任务状态后重试');
    expect(api.submitHumanDecision).toHaveBeenCalledWith(id,
      { action: 'instruct', instruction: '让活动时间更醒目' }, 1);
    expect(input).toHaveValue('让活动时间更醒目');
  });

  it('ignores pending data from an old task after the selected task changes', async () => {
    let resolveOld!: (value: api.HumanCheckpoint) => void;
    const oldPending = new Promise<api.HumanCheckpoint>((resolve) => { resolveOld = resolve; });
    vi.mocked(api.getRun).mockResolvedValue(record);
    vi.mocked(api.getPendingHumanInput).mockReturnValue(oldPending);
    const { rerender } = render(<WorkspacePage key={id} initialRunId={id} onOpenHistory={() => undefined} />);
    await waitFor(() => expect(api.getPendingHumanInput).toHaveBeenCalled());
    rerender(<WorkspacePage key="new" onOpenHistory={() => undefined} />);
    await act(async () => resolveOld(checkpoint));
    expect(screen.getByRole('button', { name: '开始生成' })).toBeInTheDocument();
    expect(screen.queryByText('请确认初版')).not.toBeInTheDocument();
  });
});
