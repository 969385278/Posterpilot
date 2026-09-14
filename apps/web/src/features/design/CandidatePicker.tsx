import { artifactUrl } from '../../api/client';
import { roleLabels, type LayoutCandidate } from '../../api/design';
import { CheckList } from './AnalysisPanel';

type Props = { runId: string; candidates: LayoutCandidate[]; selectedId: string | null; onSelect: (id: string | null) => void; disabled?: boolean };

export function CandidatePicker({ runId, candidates, selectedId, onSelect, disabled }: Props) {
  if (!candidates.length) return null;
  return <section className="candidate-picker" aria-label="注意力辅助排版候选">
    <h2>比较排版，选你更喜欢的</h2>
    <p className="design-help">同一主视觉与文字，不重新生图。候选不计入版本；选择后，到右侧提交这一轮要求。</p>
    {candidates.length === 1 && <p role="note">暂时没有通过当前检查的其他排版，可以保留当前版或调整限制后继续。</p>}
    <div className="candidate-grid">{candidates.map(candidate => <article key={candidate.id} className={selectedId === candidate.id ? 'candidate-card is-selected' : 'candidate-card'}>
      <a href={artifactUrl(runId, candidate.poster_artifact)} target="_blank" rel="noreferrer" aria-label={`查看${candidate.label}大图`}><img src={artifactUrl(runId, candidate.poster_artifact)} alt={`${candidate.label}候选海报`} /></a>
      <h3>{candidate.label}</h3>
      <p className="design-help">{candidate.attention_used_for_ranking ? '已结合注意力预测排序' : '本组未使用注意力项排序'}</p>
      <button type="button" className="secondary-action" disabled={disabled || !candidate.selectable} aria-pressed={selectedId === candidate.id} onClick={() => onSelect(selectedId === candidate.id ? null : candidate.id)}>{selectedId === candidate.id ? '取消选择' : candidate.is_current ? '采用当前排版' : '采用这个排版'}</button>
      <details><summary>查看依据与限制</summary><p>本组排序参考分：{candidate.rank_score.toFixed(1)}，不是审美分数。</p>
        <p>预测角色序列：{candidate.attention.predicted_path.length ? candidate.attention.predicted_path.map(role => roleLabels[role] ?? role).join(' → ') : '不可用'}</p>
        {candidate.attention.heatmap_artifact && <a href={artifactUrl(runId, candidate.attention.heatmap_artifact)} target="_blank" rel="noreferrer">查看此候选热力图</a>}
        {candidate.notes.map(note => <p className="design-help" key={note}>{note}</p>)}<CheckList checks={candidate.checks} />
      </details>
    </article>)}</div>
  </section>;
}
