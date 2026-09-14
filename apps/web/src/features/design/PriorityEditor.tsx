import { roleLabels, type PriorityRole } from '../../api/design';

type Props = { value: PriorityRole[]; available: PriorityRole[]; onChange: (value: PriorityRole[]) => void; disabled?: boolean };

export function PriorityEditor({ value, available, onChange, disabled }: Props) {
  function move(index: number, offset: number) {
    const next = [...value];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    onChange(next);
  }
  return <fieldset className="priority-editor" disabled={disabled}>
    <legend>希望哪些信息先被注意？</legend>
    <p className="design-help">按希望的突出顺序排列。不设置时沿用设计方案；预测不保证真实观看顺序。</p>
    {value.length > 0 && <ol>{value.map((role, index) => <li key={role}>
      <span>{index + 1}. {roleLabels[role]}</span>
      <div className="priority-actions">
        <button type="button" disabled={index === 0} aria-label={`上移${roleLabels[role]}`} onClick={() => move(index, -1)}>上移</button>
        <button type="button" disabled={index === value.length - 1} aria-label={`下移${roleLabels[role]}`} onClick={() => move(index, 1)}>下移</button>
        <button type="button" aria-label={`移除${roleLabels[role]}优先级`} onClick={() => onChange(value.filter(item => item !== role))}>移除</button>
      </div>
    </li>)}</ol>}
    <label>添加优先信息
      <select value="" onChange={event => { if (event.target.value) onChange([...value, event.target.value as PriorityRole]); }} disabled={disabled || value.length >= available.length}>
        <option value="">选择一个信息区域</option>
        {available.filter(role => !value.includes(role)).map(role => <option key={role} value={role}>{roleLabels[role]}</option>)}
      </select>
    </label>
  </fieldset>;
}
