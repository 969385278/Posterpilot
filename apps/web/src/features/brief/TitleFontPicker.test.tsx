import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { TitleFontPicker } from './TitleFontPicker';
import { BriefForm } from './BriefForm';

it('submits the explicit font with the title', () => {
  const onSubmit = vi.fn();
  render(<BriefForm onSubmit={onSubmit} isSubmitting={false} />);
  fireEvent.change(screen.getByLabelText('主标题'), { target: { value: '摄影社招新' } });
  fireEvent.change(screen.getByLabelText('主标题字体'), { target: { value: 'mashanzheng' } });
  expect(screen.getByAltText('马善政毛笔体标题字形预览')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '开始生成' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ title_font: 'mashanzheng' }));
});

it('explains unavailable previews and links the license', () => {
  render(<TitleFontPicker value="zcoolkuaile" title="招新" onChange={vi.fn()} disabled={false} />);
  fireEvent.error(screen.getByRole('img'));
  expect(screen.getByRole('status')).toHaveTextContent('字体预览暂不可用');
  expect(screen.getByRole('link')).toHaveAttribute('href', 'https://github.com/google/fonts/tree/main/ofl/zcoolkuaile');
});
