import { useEffect, useState } from 'react';
import { extractMemory, getMemoryEvents, getProfile, readMemorySource, recordMemory, retractMemory, saveMemorySource,
  type MemoryHistory, type MemoryKey, type MemoryScope, type MemorySuggestion, type UserProfile } from '../../api/memory';

const keyNames: Record<MemoryKey, string> = { style: '风格', color: '配色', title_font: '标题字体', target_audience: '受众', avoid_elements: '避免的元素' };
const scopeNames: Record<MemoryScope, string> = { all: '所有场景', cultural_event: '文化活动', campus_lecture: '校园讲座', club_recruitment: '社团招新' };
const stateNames = { active: '画像正在使用', recorded: '仅记录，不用于长期画像', superseded: '已被后续修订替代', retracted: '已撤销' };
const initialSuggestion: MemorySuggestion = { key: 'style', value: '', quote: '', scope: 'all', kind: 'explicit' };

export function MemoryPanel() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [history, setHistory] = useState<MemoryHistory | null>(null);
  const [scope, setScope] = useState<MemoryScope>('all');
  const [text, setText] = useState('');
  const [draft, setDraft] = useState(initialSuggestion);
  const [suggestions, setSuggestions] = useState<MemorySuggestion[]>([]);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setProfile(null); setError('');
    Promise.all([getProfile(scope), getMemoryEvents()]).then(([next, events]) => {
      if (active) { setProfile(next); setHistory(events); }
    }).catch(e => { if (active) setError(String(e.message)); });
    return () => { active = false; };
  }, [scope, reload]);

  async function act(operation: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }
  async function source() {
    const id = sourceId ?? crypto.randomUUID();
    await saveMemorySource(id, text.trim()); setSourceId(id); return id;
  }
  return <section className="hub-lab" aria-label="用户记忆与画像">
    <h2>记住偏好，也保留改变主意的空间</h2>
    <p>管理本机用户 local 的设计偏好。长期偏好需要你确认；本次要求和推测只保留事件记录。生成与问答中可分别选择启用记忆。</p>
    <label>查看场景<select value={scope} onChange={e => setScope(e.target.value as MemoryScope)}>{Object.entries(scopeNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    <button className="text-action" disabled={busy} onClick={() => setReload(x => x + 1)}>刷新画像</button>
    {profile && <div><h3>当前画像 · v{profile.revision}</h3>{Object.values(profile.preferences).length === 0 ? <p>当前场景还没有已确认的长期偏好。</p> : <dl>{Object.values(profile.preferences).map(item => <div key={item.id}><dt>{keyNames[item.key]} · {scopeNames[item.scope]}</dt><dd>{item.value}<blockquote>原话：{item.quote}</blockquote></dd></div>)}</dl>}</div>}
    <form className="hub-editor" onSubmit={e => { e.preventDefault(); void act(async () => {
      if (!profile) return;
      const id = await source();
      await recordMemory(id, draft, profile.revision);
      setReload(x => x + 1); setNotice(draft.kind === 'explicit' ? '已确认并更新画像，新任务可以使用。' : '已记录事件，长期画像未改变。');
      setDraft(initialSuggestion); setSuggestions([]); setText(''); setSourceId(null);
    }); }}>
      <h3>添加或修订偏好</h3>
      <label>偏好原话<textarea required maxLength={6000} value={text} onChange={e => { setText(e.target.value); setSourceId(null); setSuggestions([]); setDraft(x => ({ ...x, quote: '' })); }} placeholder="例如：以后文化活动海报优先用低饱和配色。本次标题放大。" /></label>
      <button type="button" className="secondary-action" disabled={busy || !text.trim()} onClick={() => void act(async () => {
        const id = await source(); const result = await extractMemory(id, text.trim()); setSuggestions(result.suggestions);
        setNotice(result.suggestions.length ? '提取了候选偏好，请检查后再确认。' : '没有提取到偏好，画像未改变。');
      })}>用模型提取候选（需配置模型）</button>
      {suggestions.map((item, i) => <button className="text-action" type="button" key={i} onClick={() => setDraft(item)}>选用候选：{keyNames[item.key]} · {item.value} · {item.kind}</button>)}
      <p>也可以直接填写下方内容，不需要调用模型。</p>
      <label>引用原话片段<input required value={draft.quote} maxLength={1000} onChange={e => setDraft(x => ({ ...x, quote: e.target.value }))} /></label>
      <label>偏好类别<select value={draft.key} onChange={e => setDraft(x => ({ ...x, key: e.target.value as MemoryKey }))}>{Object.entries(keyNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>偏好内容<input required maxLength={300} value={draft.value} onChange={e => setDraft(x => ({ ...x, value: e.target.value }))} /></label>
      {draft.key === 'title_font' && <small>字体标识：auto、standard、mashanzheng、longcang、zhimangxing、zcoolkuaile、zcoolqingkehuangyou、zcoolxiaowei</small>}
      <label>适用场景<select value={draft.scope} onChange={e => setDraft(x => ({ ...x, scope: e.target.value as MemoryScope }))}>{Object.entries(scopeNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <label>记忆类型<select value={draft.kind} onChange={e => setDraft(x => ({ ...x, kind: e.target.value as MemorySuggestion['kind'] }))}><option value="explicit">明确长期偏好，确认后更新画像</option><option value="temporary">仅本次要求，不更新画像</option><option value="weak">弱偏好或推测，不更新画像</option></select></label>
      <button className="primary-action" disabled={busy || !profile || !draft.quote.trim() || !text.includes(draft.quote)}>{draft.kind === 'explicit' ? '确认保存为长期偏好' : '保存事件记录'}</button>
    </form>
    <h3>事件与撤销</h3><label>撤销原因<input value={reason} maxLength={500} onChange={e => setReason(e.target.value)} placeholder="撤销前填写，例如不再喜欢这个风格" /></label>
    {history?.events.map(item => <article key={item.id}><h4>{keyNames[item.key]}：{item.value}</h4><p>{stateNames[item.state]} · {scopeNames[item.scope]} · v{item.revision}</p><blockquote>{item.quote}</blockquote>
      <button className="text-action" disabled={busy} onClick={() => void act(async () => { const value = await readMemorySource(item.source_id); setNotice(`原始消息：${value.text}`); })}>查看原始消息</button>
      {item.state !== 'retracted' && <button className="secondary-action" disabled={busy || !profile || !reason.trim()} onClick={() => void act(async () => {
        if (!profile) return;
        await retractMemory(item.id, profile.revision, reason.trim()); setReload(x => x + 1); setNotice('已撤销；不会自动恢复更早已被替代的偏好。');
      })}>撤销这条记忆</button>}
    </article>)}
    {history?.next_before && <p>当前显示最近 100 条事件；完整记录保留在记忆 API 中。</p>}
    {notice && <p role="status">{notice}</p>}{error && <p className="inline-error" role="alert">{error}</p>}
  </section>;
}
