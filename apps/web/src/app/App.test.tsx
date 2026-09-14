import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('presents the poster agent and its primary action', () => {
    render(<App />);

    expect(screen.getByRole('link', { name: 'PosterPilot 首页' })).toHaveTextContent('PosterPilot');
    expect(screen.getByRole('button', { name: '创建海报' })).toBeInTheDocument();
  });

  it('opens the workspace from the primary action', async () => {
    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '创建海报' }));

    expect(screen.getByRole('heading', { name: '创建一张可优化的海报' })).toBeInTheDocument();
  });
});
