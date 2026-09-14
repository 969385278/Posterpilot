import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { WorkspacePage } from './WorkspacePage';

describe('WorkspacePage', () => {
  it('opens the concise poster brief workspace', () => {
    render(<WorkspacePage onOpenHistory={() => undefined} />);

    expect(screen.getByRole('heading', { name: '创建一张可优化的海报' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '填入演示样例' }));
    expect(screen.getAllByDisplayValue('红楼梦研讨分享会')).toHaveLength(2);
  });
});
