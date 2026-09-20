import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { WorkspacePage } from './WorkspacePage';

describe('WorkspacePage', () => {
  it('opens the concise poster brief workspace', () => {
    render(<WorkspacePage onOpenHistory={() => undefined} />);

    expect(screen.getByRole('heading', { name: '创建一张可优化的海报' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '文化活动' }));
    expect(screen.getByLabelText('主标题')).toHaveValue('花间一课');
    expect(screen.getByLabelText('活动主题')).toHaveValue('绘画与色彩分享会');
  });
});
