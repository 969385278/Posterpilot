import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PosterPreview } from './PosterPreview';

describe('PosterPreview', () => {
  it('uses a complete portrait example before a run starts', () => {
    render(<PosterPreview status={null} />);

    const image = screen.getByRole('img', { name: '生成结果出现前的海报示例' });
    expect(image).toHaveAttribute('src', '/showcase/nebula-optimized.png');
    expect(screen.getByText(/非本次任务结果/)).toBeInTheDocument();
    expect(image).toHaveAttribute('width', '1080');
    expect(image).toHaveAttribute('height', '1440');
    expect(image.parentElement).toHaveClass('preview-poster-frame');
  });

  it('does not show an unrelated example as a failed task output', () => {
    render(<PosterPreview status="failed" />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText('生成未完成')).toBeInTheDocument();
    expect(screen.getByText(/新建任务.*重新提交/)).toBeInTheDocument();
    expect(screen.queryByText('示例')).not.toBeInTheDocument();
  });
});
