import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AgentConsole } from './AgentConsole';

const checkpoint = {
  round_number: 1,
  score: 82,
  primary_issues: ['活动信息区过密'],
  suggestion: '建议增加信息区留白。',
  citations: [
    { card_id: 'spacing-1', title: '留白原则', source_id: 'qinghua', source_pages: [18] },
  ],
  tool_traces: [
    {
      round_number: 1,
      step: 1,
      decision_summary: '调整信息区尺寸',
      tool_name: 'modify_layout' as const,
      tool_args: { actions: [] },
      observation: '已安全执行 1 个布局动作。',
      success: true,
      knowledge_card_ids: ['spacing-1'],
    },
  ],
  poster_artifact: 'poster_round_1.png',
  attention_artifact: 'attention_round_1.png',
  rounds: [],
};

describe('AgentConsole', () => {
  it('shows a human checkpoint and submits natural-language guidance', () => {
    const onInstruct = vi.fn();
    render(
      <AgentConsole
        status="waiting_for_human"
        checkpoint={checkpoint}
        events={[]}
        isSubmitting={false}
        onApprove={() => undefined}
        onInstruct={onInstruct}
        onFinish={() => undefined}
      />,
    );

    expect(screen.getByText('活动信息区过密')).toBeInTheDocument();
    expect(screen.getByText(/清华.*18/)).toBeInTheDocument();
    expect(screen.getByText('modify_layout')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('告诉 Agent 这一轮怎么改'), {
      target: { value: '保留主视觉，只增加信息区留白' },
    });
    fireEvent.click(screen.getByRole('button', { name: '提交修改要求' }));

    expect(onInstruct).toHaveBeenCalledWith('保留主视觉，只增加信息区留白');
  });
});

