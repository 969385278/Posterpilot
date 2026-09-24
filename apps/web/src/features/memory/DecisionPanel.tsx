import { useEffect, useState } from 'react';
import { listHubCases, type HubCase } from '../../api/datahub';

type Policy = { title: string; problem: string; applicable_when: string; avoid_when: string; poster_types: string[]; required_roles: string[]; trigger_terms: string[]; excluded_terms: string[]; candidate_tools: string[]; verification_rules: string[] };
type Card = { id: string; revision: number; status: 'candidate' | 'approved' | 'rejected' | 'withdrawn'; source_case_id: string; source_revision: number; origin: string; policy: Policy; audit: { revision: number; action: string; note: string }[] };
const emptyPolicy: Policy = { title: '', problem: '', applicable_when: '', avoid_when: '', poster_types: ['cultural_event'], required_roles: [], trigger_terms: [], excluded_terms: [], candidate_tools: [], verification_rules: ['goals_met', 'locks_preserved', 'no_critical_rules'] };
const statusNames = { candidate: '待审核', approved: '已发布', rejected: '已驳回', withdrawn: '已撤回' };
const toolNames: Record<string, string> = { modify_typography: '修改文字排版', modify_layout: '修改元素布局', adjust_background: '调整背景色彩', search_design_knowledge: '检索设计知识', search_poster_cases: '检索视觉案例', set_text_opacity: '调整文字透明度', align_text_group: '对齐多个文字框' };
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api/v1/datahub/decisions' + path, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || '决策卡操作失败，请检查填写内容');
  return result as T;
}

export function DecisionPanel() {
  const [cards, setCards] = useState<Card[]>([]);
  const [cases, setCases] = useState<HubCase[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [policy, setPolicy] = useState<Policy>(emptyPolicy);
  const [editing, setEditing] = useState<Card | null>(null);
  const [triggers, setTriggers] = useState('');
  const [excluded, setExcluded] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.all([request<Card[]>(''), listHubCases()]).then(([items, sources]) => {
      if (active) { setCards(items); setCases(sources); }
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [reload]);
  const source = cases.find(item => item.id === sourceId);
  const tools = [...new Set(source?.evidence.after.tool_traces.filter(item => item.success).map(item => item.tool_name) ?? [])].filter(name => name in toolNames);
  async function act(operation: () => Promise<unknown>) {
    setBusy(true); setError('');
    try { await operation(); setReload(x => x + 1); } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }
  function reset() { setEditing(null); setPolicy(emptyPolicy); setSourceId(''); setTriggers(''); setExcluded(''); }
  return <section className="hub-lab" aria-label="决策经验卡">
    <h2>把经过验证的修改，整理成可复用决策</h2>
    <p>来源须为已审核案例，含成功工具记录并通过修改目标验收。发布后只影响候选工具优先级，每个新任务仍要独立验收。</p>
    <form className="hub-editor" onSubmit={e => { e.preventDefault(); void act(async () => {
      const next = { ...policy, trigger_terms: triggers.split(/[,，]/).map(x => x.trim()).filter(Boolean), excluded_terms: excluded.split(/[,，]/).map(x => x.trim()).filter(Boolean) };
      await request(editing ? `/${editing.id}` : '', editing ? 'PUT' : 'POST', editing ? { expected_revision: editing.revision, policy: next } : { source_case_id: sourceId, policy: next });
      reset();
    }); }}>
      <h3>{editing ? '修订决策卡（保存后重新审核）' : '创建待审核决策卡'}</h3>
      <label>来源案例<select required disabled={Boolean(editing)} value={sourceId} onChange={e => {
        setSourceId(e.target.value); const item = cases.find(x => x.id === e.target.value);
        if (item) setPolicy({ ...emptyPolicy, title: item.notes.title, problem: item.notes.problem, applicable_when: item.notes.applicable_when, avoid_when: item.notes.avoid_when, poster_types: [item.evidence.after.brief.poster_type] });
      }}><option value="">选择已审核的优化案例</option>{cases.filter(item => item.status === 'approved' && item.round_number > 0).map(item => <option key={item.id} value={item.id}>{item.notes.title} · v{item.revision}</option>)}</select></label>
      {(['title', 'problem', 'applicable_when', 'avoid_when'] as const).map((key, index) => <label key={key}>{['卡片标题', '问题特征', '适用条件', '不适用情况'][index]}<textarea required maxLength={key === 'title' ? 160 : key === 'problem' ? 500 : 800} value={policy[key]} onChange={e => setPolicy(x => ({ ...x, [key]: e.target.value }))} /></label>)}
      <label>触发词（逗号分隔）<input required value={triggers} onChange={e => setTriggers(e.target.value)} placeholder="标题不醒目, 放大标题" /></label>
      <label>排除词（逗号分隔）<input value={excluded} onChange={e => setExcluded(e.target.value)} placeholder="例如：不要放大" /></label>
      <fieldset><legend>候选工具（只列来源中执行成功的工具）</legend>{tools.map(tool => <label className="inline-checkbox" key={tool}><input type="checkbox" checked={policy.candidate_tools.includes(tool)} onChange={e => setPolicy(x => ({ ...x, candidate_tools: e.target.checked ? [...x.candidate_tools, tool] : x.candidate_tools.filter(name => name !== tool) }))} />{toolNames[tool]}</label>)}</fieldset>
      <p>每次均检查修改目标、锁定条件和严重版式规则。来源版本失效或撤回后，卡片停止参与检索。</p>
      <button className="primary-action" disabled={busy || !sourceId || policy.candidate_tools.length === 0}>保存待审核卡片</button>{editing && <button type="button" className="text-action" onClick={reset}>取消编辑</button>}
    </form>
    <label>审核或撤回说明<input maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
    {cards.map(card => <article key={card.id}><h3>{card.policy.title} · v{card.revision}</h3><p>{statusNames[card.status]} · {card.origin === 'offline_demo' ? '离线测试证据' : '运行证据'} · 来源版本 {card.source_revision}</p><p>{card.policy.problem}</p><p>适用：{card.policy.applicable_when}</p><p>不适用：{card.policy.avoid_when}</p><p>候选工具：{card.policy.candidate_tools.map(name => toolNames[name] ?? name).join('、')}</p>
      <button className="text-action" disabled={busy} onClick={() => { setEditing(card); setSourceId(card.source_case_id); setPolicy(card.policy); setTriggers(card.policy.trigger_terms.join(', ')); setExcluded(card.policy.excluded_terms.join(', ')); }}>编辑并重新审核</button>
      {(['approve', 'reject', 'withdraw'] as const).map((action, i) => <button className="secondary-action" key={action} disabled={busy || !note.trim()} onClick={() => void act(() => request(`/${card.id}/review`, 'POST', { expected_revision: card.revision, action, note }))}>{['批准发布', '驳回', '撤回'][i]}</button>)}
      <details><summary>来源与审核历史</summary><p>来源案例：{card.source_case_id}</p>{card.audit.map((item, i) => <p key={i}>v{item.revision} · {item.action} · {item.note}</p>)}</details>
    </article>)}
    {error && <p role="alert" className="inline-error">{error}</p>}
  </section>;
}
