import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RunHistory } from './RunHistory';

describe('RunHistory', () => {
  it('renders an empty state and task status', () => {
    const { rerender } = render(<RunHistory runs={[]} />);
    expect(screen.getByText('还没有任务记录。创建第一张海报后，它会保留在这里。')).toBeInTheDocument();

    rerender(
      <RunHistory
        runs={[
          {
            id: '12345678-aaaa-bbbb-cccc-dddddddddddd',
            status: 'completed',
            current_node: 'finalize',
            error_message: null,
            artifacts: [],
          },
        ]}
      />,
    );
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.getByText('12345678')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '打开海报任务' })).toHaveAttribute('href', '#runs/12345678-aaaa-bbbb-cccc-dddddddddddd');
  });
});
