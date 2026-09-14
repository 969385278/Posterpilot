import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EvaluationPanel } from './EvaluationPanel';

describe('EvaluationPanel', () => {
  it('explains unavailable comparison without displaying a fake increase', () => {
    render(<EvaluationPanel result={{
      poster_initial_path: 'initial.png', poster_optimized_path: 'optimized.png',
      score_delta: null, outcome: 'not_comparable',
      comparison_reason: '两次评测的可用信号不同，不能直接比较总分。',
      evaluation_initial: { scores: { total: 80, available_weight: 75 }, attention: { availability: 'unavailable', heatmap_artifact: null } },
      evaluation_optimized: { scores: { total: 100, available_weight: 40 }, attention: { availability: 'unavailable', heatmap_artifact: null } },
    }} />);
    expect(screen.getByText('不可直接比较')).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('可用信号不同');
    expect(screen.queryByText('+20')).not.toBeInTheDocument();
  });
  it('shows the initial, optimized, and score delta values', () => {
    render(
      <EvaluationPanel
        result={{
          poster_initial_path: 'initial.png',
          poster_optimized_path: 'optimized.png',
          score_delta: 12,
          outcome: 'improved',
          evaluation_initial: {
            scores: { total: 56, available_weight: 40 },
            attention: { availability: 'unavailable', heatmap_artifact: null },
          },
          evaluation_optimized: {
            scores: { total: 68, available_weight: 40 },
            attention: { availability: 'unavailable', heatmap_artifact: null },
          },
        }}
      />,
    );

    expect(screen.getByText('初版综合评分')).toBeInTheDocument();
    expect(screen.getByText('+12')).toBeInTheDocument();
  });
});
