import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { askDesign, confirmDesign, type DesignAnswer } from '../../api/assistant';
import type { RunRecord } from '../../api/client';
import { DesignAssistant } from './DesignAssistant';

vi.mock('../../api/assistant', () => ({ askDesign: vi.fn(), confirmDesign: vi.fn() }));
const answer: DesignAnswer = {
  id: 'a1', conversation_id: 'c1', question: '标题不醒目怎么办？', answer: '可以增强标题层级。',
  run_id: 'r1', round_number: 0, degraded: false,
  citations: [{ id: 'k1', title: '视觉层级', source: '设计原则，第3页', excerpt: '标题应区别于正文。' }],
  trace: [{ tool: 'inspect_poster', summary: '已获取参考资料', success: true }],
  proposal: { scope: 'typography', instruction: '增大标题，保留主视觉。' },
};
const run = { id: 'r1', status: 'waiting_for_human' } as RunRecord;
beforeEach(() => { vi.clearAllMocks(); vi.mocked(askDesign).mockResolvedValue(answer); });

it('asks without modifying, shows evidence, and requires explicit confirmation', async () => {
  const onModified = vi.fn();
  vi.mocked(confirmDesign).mockResolvedValue({ ...run, status: 'running' });
  render(<DesignAssistant run={run} roundNumber={0} onModified={onModified} />);
  fireEvent.change(screen.getByLabelText('你的设计问题'), { target: { value: '标题不醒目怎么办？' } });
  fireEvent.click(screen.getByRole('button', { name: '发送问题' }));
  await screen.findByText('可以增强标题层级。');
  expect(confirmDesign).not.toHaveBeenCalled();
  expect(screen.getByText('视觉层级')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '确认修改这张海报' }));
  await waitFor(() => expect(onModified).toHaveBeenCalledWith(expect.objectContaining({ status: 'running' })));
  expect(confirmDesign).toHaveBeenCalledWith('a1');
  expect(screen.getByRole('button', { name: '已提交修改' })).toBeDisabled();
});

it('disables a proposal after the poster round changes', async () => {
  const props = { run, roundNumber: 0, onModified: vi.fn() };
  const view = render(<DesignAssistant {...props} />);
  fireEvent.change(screen.getByLabelText('你的设计问题'), { target: { value: '标题不醒目怎么办？' } });
  fireEvent.click(screen.getByRole('button', { name: '发送问题' }));
  await screen.findByText('可以增强标题层级。');
  view.rerender(<DesignAssistant {...props} roundNumber={1} />);
  expect(screen.getByRole('button', { name: '建议已过期，请重新提问' })).toBeDisabled();
});

it('reports failures and allows retry without clearing the question', async () => {
  vi.mocked(askDesign).mockRejectedValueOnce(new Error('服务暂不可用'));
  render(<DesignAssistant onModified={vi.fn()} />);
  fireEvent.change(screen.getByLabelText('你的设计问题'), { target: { value: '怎样配色？' } });
  fireEvent.click(screen.getByRole('button', { name: '发送问题' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('你的设计问题')).toHaveValue('怎样配色？');
  expect(screen.getByRole('button', { name: '发送问题' })).toBeEnabled();
});
