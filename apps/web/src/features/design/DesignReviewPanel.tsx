import { useState } from 'react';
import type { HumanCheckpoint, HumanDecision } from '../../api/client';
import { emptyControls, roleLabels, traitLabels, type DesignControls, type LockProperty, type PriorityRole, type TraitDirection, type TraitKey } from '../../api/design';
import { PriorityEditor } from './PriorityEditor';

type Props = { checkpoint: HumanCheckpoint; selectedCandidateId: string | null; disabled: boolean; onSubmit: (decision: HumanDecision) => void };

export function DesignReviewPanel({ checkpoint, selectedCandidateId, disabled, onSubmit }: Props) {
  const [controls, setControls] = useState<DesignControls>(() => structuredClone(checkpoint.controls ?? emptyControls()));
  const [instruction, setInstruction] = useState('');
  const available = [...new Set(checkpoint.layout?.elements.map(element => element.role).filter(role => role in roleLabels))] as PriorityRole[];
  function changeTrait(trait: TraitKey, direction: TraitDirection | '', strength?: number) {
    setControls(current => {
      const previous = current.adjustments.find(item => item.trait === trait);
      return { ...current, adjustments: [...current.adjustments.filter(item => item.trait !== trait), ...(direction ? [{ trait, direction, strength: strength ?? previous?.strength ?? 0.2 }] : [])] };
    });
  }
  function toggleLock(elementId: string, property: LockProperty, checked: boolean) {
    setControls(current => {
      const properties = current.locks.find(lock => lock.element_id === elementId)?.properties ?? [];
      const updated = checked ? [...new Set([...properties, property])] : properties.filter(item => item !== property);
      return { ...current, locks: [...current.locks.filter(lock => lock.element_id !== elementId), ...(updated.length ? [{ element_id: elementId, properties: updated }] : [])] };
    });
  }
  function submit() {
    const request = { ...controls, selected_candidate_id: selectedCandidateId };
    const text = instruction.trim();
    const hasRequest = request.adjustments.length || request.locks.length || request.attention_priority.length || selectedCandidateId;
    onSubmit(text || hasRequest ? { action: 'instruct', instruction: text || undefined, controls: request } : { action: 'approve', controls: request });
  }
  return <section className="design-review-panel" aria-label="选择本轮修改要求">
    <fieldset disabled={disabled}>
      <legend>哪些特点要改变？</legend>
      <p className="design-help">保留是明确限制；不指定则交给 Agent 判断。明暗反差与饱和度分开控制。</p>
      {(Object.keys(traitLabels) as TraitKey[]).map(trait => {
        const selected = controls.adjustments.find(item => item.trait === trait);
        const feature = checkpoint.analysis?.features.find(item => item.key === trait);
        return <div className="trait-control" key={trait}>
          <label>{traitLabels[trait]}<select value={selected?.direction ?? ''} onChange={event => changeTrait(trait, event.target.value as TraitDirection | '')}>
            <option value="">不指定</option><option value="preserve">保留</option><option value="strengthen">增强</option><option value="weaken">减弱</option>
          </select></label>
          {selected && selected.direction !== 'preserve' && <label>调整幅度<select aria-label={`${traitLabels[trait]}调整幅度`} value={selected.strength} onChange={event => changeTrait(trait, selected.direction, Number(event.target.value))}>
            <option value={0.1}>轻微</option><option value={0.2}>适中</option><option value={0.35}>明显</option><option value={0.5}>较强</option>
          </select></label>}
          {feature && <small>{feature.value == null ? '暂无测量' : `当前 ${feature.value.toFixed(3)}`}，{feature.unit}</small>}
        </div>;
      })}
    </fieldset>
    <details className="element-locks"><summary>锁定不想改变的内容（{controls.locks.length} 项）</summary>
      <p className="design-help">活动文字与主视觉构图始终保护。位置锁定包含尺寸；样式锁定包含字体、字号、颜色、行距与对齐。</p>
      {checkpoint.layout?.elements.filter(element => element.content).map(element => <fieldset disabled={disabled} key={element.id}>
        <legend>{roleLabels[element.role] ?? element.id}</legend>
        {(['position', 'typography'] as LockProperty[]).map(property => <label className="inline-checkbox" key={property}>
          <input type="checkbox" checked={Boolean(controls.locks.find(lock => lock.element_id === element.id)?.properties.includes(property))} onChange={event => toggleLock(element.id, property, event.target.checked)} />
          保留{property === 'position' ? '位置与尺寸' : '文字样式'}
        </label>)}
      </fieldset>)}
    </details>
    <details><summary>信息优先级（{controls.attention_priority.length || '沿用方案'}）</summary><PriorityEditor available={available} value={controls.attention_priority} disabled={disabled} onChange={attention_priority => setControls(current => ({ ...current, attention_priority }))} /></details>
    {selectedCandidateId && <p className="selected-candidate-note" role="status">已选排版：{checkpoint.layout_candidates?.find(candidate => candidate.id === selectedCandidateId)?.label ?? selectedCandidateId}。提交后采用；新的锁定条件若与其冲突，会提示你处理。</p>}
    <label htmlFor="structured-human-instruction">补充要求（可选）</label>
    <textarea id="structured-human-instruction" disabled={disabled} maxLength={1000} value={instruction} onChange={event => setInstruction(event.target.value)} placeholder="例如：只让背景柔和一点，不改变标题样式" />
    <p className="design-help">修改始终应用于最新海报。只选排版且未要求其他修改时，不追加自动编辑。</p>
    <button type="button" className="primary-action" disabled={disabled} onClick={submit}>{disabled ? '正在提交' : '提交这一轮要求'}</button>
    <button type="button" className="text-action" disabled={disabled} onClick={() => onSubmit({ action: 'finish' })}>结束任务，保留当前版本</button>
  </section>;
}
