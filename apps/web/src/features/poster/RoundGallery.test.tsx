import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RoundGallery } from './RoundGallery';

describe('RoundGallery', () => {
  it('switches between initial and round-level poster versions', () => {
    render(
      <RoundGallery
        runId="run-1"
        rounds={[
          {
            round_number: 1,
            poster_artifact: 'poster_round_1.png',
            attention_artifact: 'attention_round_1.png',
            score: 82,
            score_delta: 6,
            evaluation: {},
            tool_traces: [],
          },
        ]}
        initialScore={76}
        initialAttentionArtifact="attention_initial.png"
      />,
    );

    expect(screen.getByRole('img', { name: '第 1 轮海报' })).toHaveAttribute(
      'src',
      '/api/v1/runs/run-1/artifacts/poster_round_1.png',
    );
    expect(screen.getByAltText('DeepGaze 预测的视觉注意力热力图')).toHaveAttribute(
      'src', '/api/v1/runs/run-1/artifacts/attention_round_1.png',
    );
    fireEvent.click(screen.getByRole('button', { name: /初版/ }));
    expect(screen.getByRole('img', { name: '初版海报' })).toBeInTheDocument();
    expect(screen.getByAltText('DeepGaze 预测的视觉注意力热力图')).toHaveAttribute(
      'src', '/api/v1/runs/run-1/artifacts/attention_initial.png',
    );
  });
});
