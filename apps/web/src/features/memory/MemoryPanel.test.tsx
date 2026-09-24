import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import * as api from '../../api/memory';
import { MemoryPanel } from './MemoryPanel';

vi.mock('../../api/memory', () => ({ getProfile: vi.fn(), getMemoryEvents: vi.fn(), saveMemorySource: vi.fn(), extractMemory: vi.fn(), recordMemory: vi.fn(), retractMemory: vi.fn(), readMemorySource: vi.fn() }));
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getProfile).mockResolvedValue({ user_id: 'local', scope: 'all', revision: 4, preferences: {} });
  vi.mocked(api.getMemoryEvents).mockResolvedValue({ events: [], audit: [], next_before: null });
});

it('only commits an extracted suggestion after the user selects and confirms it', async () => {
  vi.mocked(api.extractMemory).mockResolvedValue({ suggestions: [{ key: 'style', value: '复古', quote: '以后用复古风格', kind: 'explicit', scope: 'all' }] });
  render(<MemoryPanel />);
  await screen.findByText('当前画像 · v4');
  fireEvent.change(screen.getByLabelText('偏好原话'), { target: { value: '以后用复古风格' } });
  fireEvent.click(screen.getByRole('button', { name: '用模型提取候选（需配置模型）' }));
  await screen.findByRole('button', { name: /选用候选：风格/ });
  expect(api.recordMemory).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: /选用候选：风格/ }));
  fireEvent.click(screen.getByRole('button', { name: '确认保存为长期偏好' }));
  await waitFor(() => expect(api.recordMemory).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ kind: 'explicit', quote: '以后用复古风格' }), 4));
});

it('preserves the draft and shows stale revision errors instead of claiming success', async () => {
  vi.mocked(api.recordMemory).mockRejectedValue(new Error('画像已更新，请刷新后再提交'));
  render(<MemoryPanel />);
  await screen.findByText('当前画像 · v4');
  fireEvent.change(screen.getByLabelText('偏好原话'), { target: { value: '以后用蓝色' } });
  fireEvent.change(screen.getByLabelText('引用原话片段'), { target: { value: '蓝色' } });
  fireEvent.change(screen.getByLabelText('偏好内容'), { target: { value: '蓝色' } });
  fireEvent.click(screen.getByRole('button', { name: '确认保存为长期偏好' }));
  await screen.findByText('画像已更新，请刷新后再提交');
  expect(screen.getByLabelText('偏好内容')).toHaveValue('蓝色');
  expect(screen.queryByText('已确认并更新画像，新任务可以使用。')).not.toBeInTheDocument();
});
