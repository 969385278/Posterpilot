import { useEffect, useState, type FormEvent } from 'react';
import { captureRun, caseQuality, editCase, hubImage, hubStats, listHubCases, retrieveExperiences, reviewCase,
  type CaseFeedback, type CaseNotes, type CaseStatus, type ExperienceReference, type HubCase, type HubStats } from '../api/datahub';
import { ThemeSelect } from '../features/theme/ThemeSelect';
import '../styles/datahub.css';

const statusNames: Record<CaseStatus, string> = { candidate: '待整理审核', approved: '已发布', rejected: '已驳回', withdrawn: '已撤回' };
const feedbackNames = { unknown: '未明确评价', accepted: '用户接受', rejected: '用户拒绝' };
const actionNames: Record<string, string> = { capture: '收集证据', edit: '修改并重审', approve: '批准发布', reject: '驳回', withdraw: '撤回' };

export function DataHubPage({ initialRunId }: { initialRunId?: string }) {
  const [cases, setCases] = useState<HubCase[]>([]);
  const [stats, setStats] = useState<HubStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [tab, setTab] = useState<'cases' | 'feedback' | 'quality' | 'retrieval'>('cases');
  const [status, setStatus] = useState('all');
  const [search, setSearch] = useState('');
  const [onlyRun, setOnlyRun] = useState(Boolean(initialRunId));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([listHubCases(), hubStats()]).then(([items, summary]) => {
      if (active) { setCases(items); setStats(summary); setError(''); }
    }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : '读取失败'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);
  async function collect() {
    if (!initialRunId) return;
    setBusy(true); setError('');
    try { await captureRun(initialRunId); setReload(value => value + 1); setNotice('已收集可用证据；重复收集不会覆盖整理和审核。'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '收集失败'); }
    finally { setBusy(false); }
  }
  function updated(item: HubCase) {
    setCases(current => current.map(value => value.id === item.id ? item : value));
    setReload(value => value + 1);
  }
  const visible = cases.filter(item => (!onlyRun || item.run_id === initialRunId)
    && (status === 'all' || item.status === status)
    && `${item.notes.title} ${item.notes.problem} ${item.notes.styles.join(' ')}`.toLowerCase().includes(search.toLowerCase()));
  const selected = cases.find(item => item.id === selectedId);
  return <main className="workspace-shell hub-shell">
    <header className="workspace-topbar"><div><a className="wordmark" href="#datahub">PosterHub</a><span>案例与反馈工作台</span></div><div className="topbar-actions"><ThemeSelect /><a className="text-action" href="#workspace">返回海报创作</a><a className="text-action" href="#history">任务历史</a></div></header>
    <section className="hub-intro"><h1>让每一次修改，都有迹可循。</h1><p>整理案例，保留反馈，审核后再供 Agent 参考。用户接受、评测分数与允许复用，是三个不同的判断。</p><p className="hub-muted">本机单用户工作台。审核记录不代表企业账号认证；没有采集的反馈保持未知，离线样例单独标记。</p></section>
    {stats && <dl className="hub-stats" aria-label="案例统计"><div><dt>全部案例</dt><dd>{stats.total}</dd></div><div><dt>待整理审核</dt><dd>{stats.statuses.candidate}</dd></div><div><dt>已发布参考</dt><dd>{stats.statuses.approved}</dd></div><div><dt>未明确评价</dt><dd>{stats.feedback.unknown}</dd></div></dl>}
    <nav className="hub-tabs" aria-label="数据工作台功能">{([['cases', '案例库'], ['feedback', '反馈记录'], ['quality', '质量与审核'], ['retrieval', '检索验证']] as const).map(([key, label]) => <button key={key} aria-pressed={tab === key} onClick={() => { setTab(key); setSelectedId(null); }}>{label}</button>)}</nav>
    {notice && <p role="status">{notice}</p>}{error && <p className="inline-error" role="alert">{error}</p>}
    {tab === 'retrieval' ? <RetrievalLab excludeRunId={initialRunId} /> : <>
      <section className="hub-filters" aria-label="筛选案例"><label>搜索案例<input value={search} onChange={event => setSearch(event.target.value)} placeholder="标题、问题或风格" /></label><label>审核状态<select value={status} onChange={event => setStatus(event.target.value)}><option value="all">全部状态</option>{Object.entries(statusNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        {initialRunId && <label className="inline-checkbox"><input type="checkbox" checked={onlyRun} onChange={event => setOnlyRun(event.target.checked)} />仅当前任务</label>}
        <button className="secondary-action" disabled={loading || busy} onClick={() => setReload(value => value + 1)}>刷新</button>{initialRunId && <button className="secondary-action" disabled={busy} onClick={() => void collect()}>{busy ? '收集中…' : '重新收集此任务'}</button>}
      </section>
      {loading ? <p role="status">正在读取案例与反馈…</p> : visible.length === 0 ? <section className="hub-empty"><h2>这里还没有匹配的案例</h2><p>新版生成任务会自动收集每轮证据。完成海报后，在这里整理适用条件和反馈，再决定是否发布。</p><a className="primary-action" href="#workspace">去创建一张海报</a></section> : <div className="hub-catalog">{visible.map(item => <article key={item.id} className={`hub-card ${selectedId === item.id ? 'is-selected' : ''}`}><button className="hub-card-open" aria-label={`查看 ${item.notes.title}`} onClick={() => setSelectedId(item.id)}><img src={hubImage(item.id)} alt={`${item.notes.title}海报`} loading="lazy" /><div><span className="hub-status">{statusNames[item.status]} · v{item.revision}</span><h2>{item.notes.title}</h2><p>{item.origin === 'offline_demo' ? '离线测试素材' : '运行生成记录'} · {feedbackNames[item.feedback.verdict]}</p><p>{tab === 'feedback' ? item.feedback.comment || '尚未记录明确的用户反馈' : item.notes.problem || '尚未整理问题与适用条件'}</p>{tab === 'quality' && <p>{item.notes.rights === 'unconfirmed' ? '使用授权待确认' : '已说明使用授权'} · 修改后需重审</p>}</div></button></article>)}</div>}
      {selected && <CaseEditor key={`${selected.id}:${selected.revision}`} item={selected} onUpdated={updated} onClose={() => setSelectedId(null)} />}
    </>}
  </main>;
}

function CaseEditor({ item, onUpdated, onClose }: { item: HubCase; onUpdated: (item: HubCase) => void; onClose: () => void }) {
  const [notes, setNotes] = useState<CaseNotes>(item.notes);
  const [styleInput, setStyleInput] = useState(item.notes.styles.join(', '));
  const [feedback, setFeedback] = useState<CaseFeedback>(item.feedback);
  const [reviewNote, setReviewNote] = useState('');
  const [issues, setIssues] = useState<string[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const draftNotes = { ...notes, styles: styleInput.split(/[,，]/).map(value => value.trim()).filter(Boolean) };
  const dirty = JSON.stringify(draftNotes) !== JSON.stringify(item.notes) || JSON.stringify(feedback) !== JSON.stringify(item.feedback);
  useEffect(() => {
    let active = true;
    caseQuality(item.id).then(value => { if (active) setIssues(value.issues); }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : '检查失败'); });
    return () => { active = false; };
  }, [item.id]);
  function updateNote(field: keyof CaseNotes, value: string) { setNotes(current => ({ ...current, [field]: value })); }
  function updateFeedback(patch: Partial<CaseFeedback>) { setFeedback(current => ({ ...current, ...patch, source: item.origin === 'offline_demo' ? 'demo_fixture' : 'explicit_user' })); }
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { onUpdated(await editCase(item, draftNotes, feedback)); } catch (reason) { setError(reason instanceof Error ? reason.message : '保存失败'); } finally { setBusy(false); }
  }
  async function review(action: 'approve' | 'reject' | 'withdraw') {
    setBusy(true); setError('');
    try { onUpdated(await reviewCase(item, action, reviewNote)); } catch (reason) { setError(reason instanceof Error ? reason.message : '审核失败'); } finally { setBusy(false); }
  }
  const comparison = item.evidence.comparison;
  return <section className="hub-detail" aria-label="案例详情">
    <header><div><h2>{item.notes.title}</h2><p>{statusNames[item.status]} · 整理版本 {item.revision} · <a href={`#runs/${item.run_id}`}>打开来源任务</a></p></div><button className="text-action" onClick={onClose}>收起详情</button></header>
    <div className="hub-detail-grid"><div>
      <div className="hub-comparison">{item.before_image_hash && <figure><img src={hubImage(item.id, true)} alt="修改前海报" /><figcaption>修改前</figcaption></figure>}<figure><img src={hubImage(item.id)} alt="本轮海报" /><figcaption>本轮结果 · {item.round_number === 0 ? '初版' : `第 ${item.round_number} 轮`}</figcaption></figure></div>
      <p>{comparison.delta === null ? `不可直接比较分数：${comparison.reason}` : `同条件综合分变化：${comparison.delta > 0 ? '+' : ''}${comparison.delta}。不是审美或因果效果结论。`}</p>
      <h3>原始修改意见</h3><p>{item.evidence.after.instruction || '初版没有修改意见'}</p><h3>实际工具动作</h3>
      {item.evidence.after.tool_traces.length ? <ol>{item.evidence.after.tool_traces.map((trace, index) => <li key={index}><strong>{trace.tool_name} · {trace.success ? '执行成功' : '执行失败'}</strong><p>{trace.observation}</p><details><summary>查看参数</summary><pre>{JSON.stringify(trace.tool_args, null, 2)}</pre></details></li>)}</ol> : <p>本轮没有工具动作，不推断发生过优化。</p>}
      <details><summary>不可编辑的来源证据与布局</summary><p>证据校验值：{item.evidence_hash}</p><pre>{JSON.stringify(item.evidence, null, 2)}</pre></details>
    </div><div><form className="hub-editor" onSubmit={event => void save(event)}><h3>整理可复用经验</h3>
      <label>案例标题<input required maxLength={160} value={notes.title} onChange={event => updateNote('title', event.target.value)} /></label>
      <label>风格标签（逗号分隔）<input value={styleInput} onChange={event => setStyleInput(event.target.value)} /></label>
      {([['problem', '问题描述'], ['lesson', '复用建议'], ['applicable_when', '适用条件'], ['avoid_when', '限制与不适用情况']] as const).map(([key, label]) => <label key={key}>{label}<textarea value={notes[key]} maxLength={key === 'lesson' ? 1600 : key === 'problem' ? 1000 : 800} onChange={event => updateNote(key, event.target.value)} /></label>)}
      <h3>明确的用户反馈</h3><label>是否接受<select value={feedback.verdict} onChange={event => updateFeedback({ verdict: event.target.value as CaseFeedback['verdict'] })}>{Object.entries(feedbackNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>反馈原话<textarea value={feedback.comment} maxLength={1000} onChange={event => updateFeedback({ comment: event.target.value })} placeholder="没有收集反馈就留空，不把结束任务当作接受" /></label>
      <label className="inline-checkbox"><input type="checkbox" checked={notes.rights === 'own_or_authorized'} onChange={event => setNotes(current => ({ ...current, rights: event.target.checked ? 'own_or_authorized' : 'unconfirmed' }))} />确认图片与反馈允许在本项目中复用</label><label>授权依据<input value={notes.rights_note} maxLength={500} onChange={event => updateNote('rights_note', event.target.value)} placeholder="说明自有素材或授权来源，不自动推断" /></label>
      <button className="primary-action" disabled={busy || !dirty} type="submit">保存整理信息，转为待审核</button>
    </form><section className="hub-review" aria-label="质量审核"><h3>审核与发布</h3>
      {issues === null ? <p>正在检查当前已保存版本…</p> : issues.length ? <ul>{issues.map(issue => <li key={issue}>{issue}</li>)}</ul> : <p>基础资料检查通过。请继续人工检查经验是否可信、条件是否清楚。</p>}
      <label>审核说明<textarea value={reviewNote} maxLength={1000} onChange={event => setReviewNote(event.target.value)} placeholder="为什么允许复用、驳回或撤回" /></label>{dirty && <p>有未保存内容，请先保存后再审核。</p>}
      <div className="hub-actions"><button className="primary-action" disabled={busy || dirty || !reviewNote.trim() || issues === null || issues.length > 0 || item.status === 'approved'} onClick={() => void review('approve')}>批准作为参考</button><button className="secondary-action" disabled={busy || dirty || !reviewNote.trim()} onClick={() => void review('reject')}>驳回</button><button className="secondary-action" disabled={busy || dirty || !reviewNote.trim()} onClick={() => void review('withdraw')}>撤回参考</button></div><p className="hub-muted">发布不是“普遍优秀”的认证；撤回后新检索不再返回，历史证据仍保留。</p>
    </section>{error && <p className="inline-error" role="alert">{error} 可刷新页面获取最新版本。</p>}<details><summary>查看版本与审核记录（{item.audit.length}）</summary><ol>{item.audit.map((audit, index) => <li key={index}>v{audit.revision} · {actionNames[audit.action] ?? audit.action}<p>{audit.note}</p><small>{new Date(audit.at).toLocaleString()}</small>{audit.snapshot && <details><summary>查看当时的整理内容与反馈</summary><pre className="hub-json">{JSON.stringify(audit.snapshot, null, 2)}</pre></details>}</li>)}</ol></details></div></div>
  </section>;
}

function RetrievalLab({ excludeRunId }: { excludeRunId?: string }) {
  const [query, setQuery] = useState('标题不醒目');
  const [posterType, setPosterType] = useState('cultural_event');
  const [demo, setDemo] = useState(false);
  const [matches, setMatches] = useState<ExperienceReference[] | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function search(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMatches(null);
    try { setMatches((await retrieveExperiences(query, posterType, demo, excludeRunId)).matches); } catch (reason) { setError(reason instanceof Error ? reason.message : '检索失败'); } finally { setBusy(false); }
  }
  return <section className="hub-lab"><h2>先验证参考是否合适，再讨论效果提升</h2><p>只检查案例检索，不调用生成模型。同一任务的案例会被排除，未发布和已撤回案例不会返回。</p>
    <form className="hub-filters" onSubmit={event => void search(event)}><label>新任务的问题<input required maxLength={1000} value={query} onChange={event => setQuery(event.target.value)} /></label><label>活动类型<select value={posterType} onChange={event => setPosterType(event.target.value)}><option value="cultural_event">文化活动</option><option value="campus_lecture">校园讲座</option><option value="club_recruitment">社团招新</option></select></label><label className="inline-checkbox"><input type="checkbox" checked={demo} onChange={event => setDemo(event.target.checked)} />包含离线演示案例</label><button className="primary-action" disabled={busy || !query.trim()}>{busy ? '检索中…' : '运行检索对照'}</button></form>
    {error && <p role="alert" className="inline-error">{error}</p>}{matches !== null && <div className="hub-lab-results"><section><h3>关闭案例参考</h3><p>不向 Agent 提供历史经验，保留原来的设计知识检索与生成优化流程。</p></section><section><h3>开启案例参考 · {matches.length} 条</h3>{matches.length ? matches.map(item => <article key={item.case_id}><strong>{item.problem}</strong><p>{item.lesson}</p><p>适用：{item.applicable_when}</p><p>限制：{item.avoid_when}</p><small>来源 {item.case_id.slice(0, 8)} · v{item.revision} · {item.origin === 'offline_demo' ? '离线样例' : '运行记录'}</small></article>) : <p>没有匹配参考，Agent 应继续原流程，不编造历史经验。</p>}</section></div>}
    <p className="hub-muted">这是输入参考对照，不是生成质量实验。要验证效果，需用固定的新任务比较实际结果，并保留失败、耗时和费用。</p>
  </section>;
}
