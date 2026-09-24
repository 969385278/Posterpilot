import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { IntentInput } from './IntentInput';

afterEach(() => vi.unstubAllGlobals());
it('previews requirements and only sends modifications after confirmation', async () => {
  const onModify = vi.fn();
  const controls = { locks: [{ element_id: 'event_info', properties: ['position'] }], adjustments: [] };
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ intent: 'modify', explanation: '', warnings: [], can_apply: true, round_number: 0, controls, requirements: [{ goal: '时间地点位置不变', quote: '时间地点位置不变', hard_constraint: true }] }) }));
  render(<IntentInput runId="run" roundNumber={0} disabled={false} onGenerate={vi.fn()} onQuestion={vi.fn()} onModify={onModify} />);
  fireEvent.change(screen.getByLabelText('海报需求'), { target: { value: '时间地点位置不变' } });
  fireEvent.click(screen.getByRole('button', { name: '解析需求' }));
  await screen.findByText('保留条件：时间地点位置不变');
  expect(onModify).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '确认这些要求并修改' }));
  expect(onModify).toHaveBeenCalledWith({ action: 'instruct', instruction: '时间地点位置不变', controls });
});

it('does not apply a preview after the current poster advances to another round', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ intent: 'modify', explanation: '', warnings: [], can_apply: true, round_number: 0, controls: {}, requirements: [] }) }));
  const props = { runId: 'run', roundNumber: 0, disabled: false, onGenerate: vi.fn(), onQuestion: vi.fn(), onModify: vi.fn() };
  const view = render(<IntentInput {...props} />);
  fireEvent.change(screen.getByLabelText('海报需求'), { target: { value: '放大标题' } });
  fireEvent.click(screen.getByRole('button', { name: '解析需求' }));
  await screen.findByRole('button', { name: '确认这些要求并修改' });
  view.rerender(<IntentInput {...props} roundNumber={1} />);
  expect(screen.getByRole('button', { name: '海报轮次已变化，请重新解析' })).toBeDisabled();
  expect(props.onModify).not.toHaveBeenCalled();
});
