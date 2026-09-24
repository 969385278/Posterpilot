import { useState } from 'react';
import type { HumanDecision, PosterBriefInput } from '../../api/client';
import type { DesignControls } from '../../api/design';

type Resolution = {
  intent: 'generate' | 'modify' | 'question' | 'out_of_scope' | 'clarify';
  explanation: string; warnings: string[]; can_apply: boolean;
  round_number: number | null;
  brief: PosterBriefInput | null; controls: DesignControls;
  requirements: { target: string; goal: string; quote: string; hard_constraint: boolean }[];
};
type Props = { runId?: string; roundNumber?: number; disabled: boolean; onGenerate: (brief: Partial<PosterBriefInput>) => void; onQuestion: (text: string) => void; onModify: (decision: HumanDecision) => void };
const names = { generate: '生成新海报', modify: '修改当前海报', question: '设计问答', out_of_scope: '超出海报设计范围', clarify: '需要更明确的描述' };

export function IntentInput({ runId, roundNumber, disabled, onGenerate, onQuestion, onModify }: Props) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [resolution, setResolution] = useState<Resolution | null>(null);
  const [resolvedText, setResolvedText] = useState('');
  async function resolve() {
    setBusy(true); setError(''); setResolution(null);
    try {
      const response = await fetch('/api/v1/intents/resolve', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, run_id: runId }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.error?.message || '需求解析暂时不可用');
      setResolution(value); setResolvedText(text);
    } catch (e) { setError(e instanceof Error ? e.message : '解析失败'); }
    finally { setBusy(false); }
  }
  return <section className="design-assistant" aria-label="一句话需求">
    <h2>先说说你想做什么</h2>
    <form onSubmit={e => { e.preventDefault(); void resolve(); }}>
      <label>海报需求<textarea required maxLength={1000} value={text} disabled={busy || disabled} placeholder="例如：放大标题，降低背景饱和度，时间地点的位置不变" onChange={e => { setText(e.target.value); setResolution(null); }} /></label>
      <button className="secondary-action" disabled={busy || disabled || !text.trim()}>{busy ? '正在理解…' : '解析需求'}</button>
    </form>
    {resolution && <div><h3>{names[resolution.intent]}</h3><p>{resolution.explanation}</p>
      {resolution.requirements.length > 0 && <ul>{resolution.requirements.map((item, i) => <li key={i}>{item.hard_constraint ? '保留条件' : resolution.intent === 'modify' ? '修改目标' : '设计要求'}：{item.goal}</li>)}</ul>}
      {resolution.warnings.map((item, i) => <p key={i}>{item}</p>)}
      {resolution.controls.fact_edits?.map(edit => <p key={edit.field}>文字替换：{edit.before} → {edit.after}</p>)}
      {resolution.intent === 'generate' && <button className="secondary-action" disabled={disabled} onClick={() => { onGenerate(resolution.brief ?? { notes: resolvedText }); setResolution(null); }}>填入下方需求表</button>}
      {resolution.intent === 'question' && <button className="secondary-action" disabled={disabled} onClick={() => { onQuestion(resolvedText); setResolution(null); }}>交给设计助手</button>}
      {resolution.intent === 'modify' && <button className="primary-action" disabled={disabled || !resolution.can_apply || resolution.round_number !== roundNumber} onClick={() => {
        onModify({ action: 'instruct', instruction: resolvedText, controls: resolution.controls }); setResolution(null);
      }}>{resolution.can_apply && resolution.round_number !== roundNumber ? '海报轮次已变化，请重新解析' : '确认这些要求并修改'}</button>}
    </div>}
    {error && <p role="alert" className="inline-error">{error}</p>}
  </section>;
}
