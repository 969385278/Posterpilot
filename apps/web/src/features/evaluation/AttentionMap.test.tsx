import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AttentionMap } from './AttentionMap';

describe('AttentionMap', () => {
  it('labels unavailable predictions and available heatmaps correctly', () => {
    const { rerender } = render(<AttentionMap availability="unavailable" />);
    expect(screen.getByText('DeepGaze 当前不可用，未生成热力图。')).toBeInTheDocument();

    rerender(<AttentionMap availability="available" imageUrl="/attention.png" />);
    expect(screen.getByAltText('DeepGaze 预测的视觉注意力热力图')).toBeInTheDocument();
    expect(screen.getByText(/这是模型预测，不是真实用户眼动/)).toBeInTheDocument();
  });
});
