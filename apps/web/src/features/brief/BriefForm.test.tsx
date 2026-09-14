import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { BriefForm } from './BriefForm';

it('requires only a title and uses it as the default topic', () => {
  const submit = vi.fn();
  render(<BriefForm onSubmit={submit} isSubmitting={false} />);
  const title = screen.getByLabelText('主标题');
  expect(title).toBeRequired();
  for (const label of ['活动主题', '时间', '地点', '主办方', '目标受众', '副标题']) {
    expect(screen.getByLabelText(label)).not.toBeRequired();
  }
  fireEvent.change(title, { target: { value: '摄影社招新' } });
  fireEvent.click(screen.getByRole('button', { name: '开始生成' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({
    title: '摄影社招新', topic: '摄影社招新', event_time: '', location: '', organizer: '',
  }));
});

it('preserves an explicit topic and removes priorities for cleared optional content', () => {
  const submit = vi.fn();
  render(<BriefForm onSubmit={submit} isSubmitting={false} />);
  fireEvent.change(screen.getByLabelText('主标题'), { target: { value: '加入我们' } });
  fireEvent.change(screen.getByLabelText('活动主题'), { target: { value: '摄影社招新' } });
  fireEvent.click(screen.getByText('设置注意力辅助排版'));
  expect(screen.queryByRole('option', { name: '主办方' })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('主办方'), { target: { value: '摄影社' } });
  fireEvent.change(screen.getByLabelText('添加优先信息'), { target: { value: 'organizer' } });
  fireEvent.change(screen.getByLabelText('主办方'), { target: { value: '' } });
  fireEvent.click(screen.getByRole('button', { name: '开始生成' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ topic: '摄影社招新', attention_priority: [] }));
});
