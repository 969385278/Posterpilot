import { roleLabels, type DesignControls, type ElementGoal, type PosterLayout } from '../../api/design';

export function ElementGoalsEditor({ layout, controls, disabled, onChange }: {
  layout?: PosterLayout | null; controls: DesignControls; disabled: boolean;
  onChange: (goals: ElementGoal[]) => void;
}) {
  const elements = layout?.elements.filter(element => element.content && element.role !== 'main_visual') ?? [];
  const goals = controls.element_goals ?? [];
  function change(kind: ElementGoal['kind'], id: string, goal?: ElementGoal) {
    onChange([...goals.filter(item => !(item.kind === kind && item.element_id === id)), ...(goal ? [goal] : [])]);
  }
  return <details><summary>文字透明度与文字框对齐（{goals.length} 项）</summary>
    <p className="design-help">不透明度 100% 表示完全不透明；目标会在渲染后验收。文字框对齐不代表字形边缘对齐，调整仍须遵守锁定与可读性要求。</p>
    {elements.map(element => {
      const opacity = goals.find(item => item.kind === 'opacity' && item.element_id === element.id);
      const alignment = goals.find(item => item.kind === 'alignment' && item.element_id === element.id);
      const name = roleLabels[element.role] ?? element.id;
      return <fieldset key={element.id} disabled={disabled}>
        <legend>{name}精确目标</legend>
        <label>{name}不透明度<select value={opacity?.kind === 'opacity' ? opacity.opacity : ''} onChange={e => change('opacity', element.id, e.target.value ? { kind: 'opacity', element_id: element.id, opacity: Number(e.target.value) } : undefined)}>
          <option value="">不指定</option>{[1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3].map(value => <option key={value} value={value}>{Math.round(value * 100)}%</option>)}
          {opacity?.kind === 'opacity' && ![1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3].includes(opacity.opacity) && <option value={opacity.opacity}>{opacity.opacity * 100}%</option>}
        </select></label>
        <label>{name}文字框对齐参考<select value={alignment?.kind === 'alignment' ? alignment.reference_id : ''} onChange={e => change('alignment', element.id, e.target.value ? { kind: 'alignment', element_id: element.id, reference_id: e.target.value, edge: alignment?.kind === 'alignment' ? alignment.edge : 'left' } : undefined)}>
          <option value="">不指定</option>{elements.filter(item => item.id !== element.id).map(item => <option key={item.id} value={item.id}>{roleLabels[item.role] ?? item.id}</option>)}
        </select></label>
        {alignment?.kind === 'alignment' && <label>{name}文字框对齐边<select value={alignment.edge} onChange={e => change('alignment', element.id, { ...alignment, edge: e.target.value as 'left' | 'center' | 'right' })}>
          <option value="left">左边</option><option value="center">中心</option><option value="right">右边</option>
        </select></label>}
      </fieldset>;
    })}
  </details>;
}
