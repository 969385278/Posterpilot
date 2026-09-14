import { useState } from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { selectReferenceAspect, type ReferenceSelection } from '../../api/design';
import { DesignReviewPanel } from './DesignReviewPanel';
import { CandidatePicker } from './CandidatePicker';
import { PriorityEditor } from './PriorityEditor';
import { candidateFixture, checkpointFixture } from './fixtures';

describe('controlled design requests', () => {
  it('moves a reference dimension without mutating the old choices', () => {
    const current: ReferenceSelection[] = [{ case_id: 'first', aspects: ['palette', 'composition'] }];
    expect(selectReferenceAspect(current, 'second', 'palette', true)).toEqual([
      { case_id: 'first', aspects: ['composition'] }, { case_id: 'second', aspects: ['palette'] },
    ]);
    expect(current[0].aspects).toEqual(['palette', 'composition']);
    expect(selectReferenceAspect(current, 'second', 'palette', false)).toEqual(current);
  });
  it('rejects four source posters without changing existing selections', () => {
    const current: ReferenceSelection[] = [{ case_id: 'a', aspects: ['palette'] }, { case_id: 'b', aspects: ['typography'] }, { case_id: 'c', aspects: ['composition'] }];
    expect(() => selectReferenceAspect(current, 'd', 'hierarchy', true)).toThrow('最多参考三张');
    expect(current).toHaveLength(3);
  });
  it('submits structured-only instructions, locks, priority, and the selected candidate', () => {
    const onSubmit = vi.fn();
    render(<DesignReviewPanel checkpoint={{ ...checkpointFixture, layout_candidates: [candidateFixture] }} selectedCandidateId={candidateFixture.id} disabled={false} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText('背景明暗反差'), { target: { value: 'weaken' } });
    fireEvent.change(screen.getByLabelText('背景明暗反差调整幅度'), { target: { value: '0.35' } });
    const titleGroup = screen.getByRole('group', { name: '标题', hidden: true });
    fireEvent.click(within(titleGroup).getByLabelText('保留文字样式'));
    fireEvent.change(screen.getByLabelText('添加优先信息'), { target: { value: 'event_info' } });
    fireEvent.click(screen.getByRole('button', { name: '提交这一轮要求' }));
    expect(onSubmit).toHaveBeenCalledWith({ action: 'instruct', instruction: undefined, controls: {
      adjustments: [{ trait: 'background_contrast', direction: 'weaken', strength: 0.35 }],
      locks: [{ element_id: 'title', properties: ['typography'] }], attention_priority: ['event_info'], selected_candidate_id: candidateFixture.id,
    } });
  });
  it('restores persisted controls and submits finish without stale controls', () => {
    const onSubmit = vi.fn();
    render(<DesignReviewPanel checkpoint={{ ...checkpointFixture, controls: { adjustments: [{ trait: 'background_saturation', direction: 'preserve', strength: 0.2 }], locks: [], attention_priority: ['title'] } }} selectedCandidateId={null} disabled={false} onSubmit={onSubmit} />);
    expect(screen.getByLabelText('背景饱和度')).toHaveValue('preserve');
    fireEvent.click(screen.getByRole('button', { name: '结束任务，保留当前版本' }));
    expect(onSubmit).toHaveBeenCalledWith({ action: 'finish' });
  });
  it('disables submission while a request is pending', () => {
    render(<DesignReviewPanel checkpoint={checkpointFixture} selectedCandidateId={null} disabled onSubmit={vi.fn()} />);
    expect(screen.getByLabelText('背景明暗反差')).toBeDisabled();
    expect(screen.getByRole('button', { name: '正在提交' })).toBeDisabled();
  });
  it('reorders and removes priorities', () => {
    function Harness() {
      const [value, setValue] = useState<('title' | 'event_info')[]>(['title', 'event_info']);
      return <PriorityEditor value={value} available={['title', 'event_info']} onChange={next => setValue(next as typeof value)} />;
    }
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: '上移活动信息' }));
    expect(screen.getByText('1. 活动信息')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '移除标题优先级' }));
    expect(screen.queryByRole('button', { name: '移除标题优先级' })).not.toBeInTheDocument();
  });
  it('shows degraded attention honestly and toggles candidate selection', () => {
    const onSelect = vi.fn();
    const props = { runId: 'run', candidates: [candidateFixture], selectedId: null, onSelect };
    const { rerender } = render(<CandidatePicker {...props} />);
    expect(screen.getByText('本组未使用注意力项排序')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '采用这个排版' }));
    expect(onSelect).toHaveBeenCalledWith(candidateFixture.id);
    rerender(<CandidatePicker {...props} selectedId={candidateFixture.id} />);
    fireEvent.click(screen.getByRole('button', { name: '取消选择' }));
    expect(onSelect).toHaveBeenLastCalledWith(null);
    rerender(<CandidatePicker {...props} candidates={[{ ...candidateFixture, selectable: false }]} />);
    expect(screen.getByRole('button', { name: '采用这个排版' })).toBeDisabled();
  });
});
