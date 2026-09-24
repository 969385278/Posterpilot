import { useEffect, useState } from 'react';

type Tool = { name: string; description: string; status: string; enabled: boolean; revision: number; fingerprint: string; parameters: unknown; implementation: string; release: { audit: { action: string; reviewer: string; note: string; revision: number }[] } | null };
type Report = { id: string; tool: string; state: string; tests?: number; failures?: number; skipped?: number; created_at: string; fingerprint: string; error?: string; log_tail?: string };
type Gap = { id: string; revision: number; category: string; status: string; signature: string; origin: string; occurrences: number; observations: { id: string; run_id: string; case_id: string | null; detail: string }[] };
const labels: Record<string, string> = { bundled: '内置可用', candidate: '待验证发布', published: '已发布', withdrawn: '已撤回', stale: '代码已变化，需重启并重审', queued: '排队中', running: '测试中', passed: '通过', failed: '失败', cancelled: '已作废', open: '待分析', triaged: '已分类', resolved: '已验收解决', resolution_stale: '解决证据已失效' };
const categories: Record<string, string> = { unclassified: '待人工判断', strategy_error: '策略或参数错误', capability_gap: '工具能力缺口', infrastructure: '模型、依赖或测量不可用' };

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api/v1/datahub/harness' + path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || '工具治理请求失败');
  return result as T;
}

export function HarnessPanel() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [reload, setReload] = useState(0);
  const [reviewer, setReviewer] = useState('');
  const [note, setNote] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    Promise.all([request<Tool[]>('/tools'), request<Report[]>('/reports'), request<Gap[]>('/gaps')]).then(([catalog, checks, issues]) => {
      if (!active) return;
      setTools(catalog); setReports(checks); setGaps(issues);
      if (checks.some(item => ['queued', 'running'].includes(item.state))) timer = setTimeout(() => setReload(x => x + 1), 2000);
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; clearTimeout(timer); };
  }, [reload]);
  async function act(operation: () => Promise<unknown>, message = '') {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); setReload(x => x + 1); setNotice(message); }
    catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }
  const testing = reports.some(item => ['queued', 'running'].includes(item.state));
  return <section className="hub-lab" aria-label="工具发布与能力缺口">
    <h2>先验证工具，再交给 Agent 使用</h2>
    <p>新工具从代码注册表进入候选目录。发布需要当前实现的回归报告和人工实现审查；代码、依赖变化或工具撤回后，调用会被拦截。</p>
    <div className="hub-filters"><label>审查人<input value={reviewer} maxLength={80} onChange={e => setReviewer(e.target.value)} /></label><label>审查或撤回说明<input value={note} maxLength={1000} onChange={e => setNote(e.target.value)} /></label>
      <label className="inline-checkbox"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />已检查实现、参数范围与锁定保护</label>
      <button className="secondary-action" disabled={busy} onClick={() => setReload(x => x + 1)}>刷新目录与报告</button>
    </div>
    {tools.map(tool => {
      const report = reports.find(item => item.tool === tool.name && item.state === 'passed' && item.fingerprint === tool.fingerprint);
      return <article key={tool.name}><h3>{tool.name} · {labels[tool.status] ?? tool.status}</h3><p>{tool.description}</p>
        <p>{tool.enabled ? 'Agent 当前可调用' : 'Agent 当前不可调用'} · 发布记录 v{tool.revision}</p>
        <details><summary>查看参数与实现位置</summary><p>{tool.implementation}</p><pre>{JSON.stringify(tool.parameters, null, 2)}</pre><p>代码指纹：{tool.fingerprint}</p></details>
        <div className="hub-actions"><button className="secondary-action" disabled={busy || testing} onClick={() => void act(() => request(`/tools/${tool.name}/validate`, {}), '已启动隔离回归，页面将自动更新报告。')}>运行参数与渲染回归</button>
          <button className="primary-action" disabled={busy || !report || !reviewed || !reviewer.trim() || !note.trim()} onClick={() => void act(() => request(`/tools/${tool.name}/review`, { expected_revision: tool.revision, action: 'publish', report_id: report?.id, implementation_reviewed: reviewed, reviewer, note }), '已发布当前通过验证的工具版本。')}>审核并发布</button>
          <button className="secondary-action" disabled={busy || !tool.enabled || !reviewer.trim() || !note.trim()} onClick={() => void act(() => request(`/tools/${tool.name}/review`, { expected_revision: tool.revision, action: 'withdraw', reviewer, note }), '已撤回，后续调用将被拦截。')}>撤回工具</button></div>
        {tool.release && <details><summary>发布历史</summary>{tool.release.audit.map((entry, i) => <p key={i}>v{entry.revision} · {entry.action} · {entry.reviewer}：{entry.note}</p>)}</details>}
      </article>;
    })}
    <h3>回归报告</h3>{reports.length === 0 && <p>尚无发布回归报告。</p>}
    {reports.map(report => <article key={report.id}><strong>{report.tool} · {labels[report.state] ?? report.state}</strong><p>{report.tests !== undefined ? `${report.tests} 项测试，${report.failures} 项失败，${report.skipped} 项跳过` : '等待测试结果'}</p>{report.error && <p>{report.error}</p>}
      {['queued', 'running'].includes(report.state) && <button className="text-action" disabled={busy} onClick={() => void act(() => request(`/reports/${report.id}/cancel`, {}), '报告已作废，不能用于发布。已启动的测试可能仍在结束中。')}>作废此次报告</button>}
      {report.log_tail && <details><summary>查看测试输出</summary><pre>{report.log_tail}</pre></details>}
    </article>)}
    <h3>重复失败与未解决要求</h3><p>系统按真实工具失败、目标验收和明确拒绝反馈归集证据；由人工区分策略问题、能力缺口和依赖问题。</p>
    <button className="secondary-action" disabled={busy} onClick={() => void act(() => request('/collect', {}), '已归集来源证据，重复采集不会增加次数。')}>重新归集运行证据</button>
    {gaps.length === 0 && <p>还没有归集到失败或未验证项；这不代表所有能力已具备。</p>}
    {gaps.map(gap => <GapEditor key={`${gap.id}:${gap.revision}`} gap={gap} disabled={busy} onSave={body => act(() => request(`/gaps/${gap.id}/triage`, body), '已保存分类与验收记录。')} />)}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert" className="inline-error">{error}</p>}
  </section>;
}

function GapEditor({ gap, disabled, onSave }: { gap: Gap; disabled: boolean; onSave: (body: unknown) => Promise<void> }) {
  const [category, setCategory] = useState(gap.category);
  const [note, setNote] = useState('');
  const [resolution, setResolution] = useState('');
  const [tool, setTool] = useState('');
  return <article><h4>{gap.signature} · {gap.occurrences} 次</h4><p>{labels[gap.status] ?? gap.status} · {gap.origin === 'offline_demo' ? '离线测试证据' : '运行证据'}</p>
    <details><summary>查看来源与失败原因</summary>{gap.observations.map(item => <p key={item.id}><a href={`#runs/${item.run_id}`}>来源任务</a> · {item.case_id ? `案例 ${item.case_id}` : '任务失败，尚未形成海报案例'}<br />{item.detail}</p>)}</details>
    <form className="hub-editor" onSubmit={e => { e.preventDefault(); void onSave({ expected_revision: gap.revision, category, note, resolution_case_ids: resolution.trim() ? resolution.trim().split(/[\s,，]+/) : [], resolution_tool: tool.trim() || null }); }}>
      <label>问题分类<select value={category} onChange={e => setCategory(e.target.value)}>{Object.entries(categories).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>
      <label>判断依据<textarea required maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
      <label>解决证据案例 ID（可选，多个用换行或逗号分隔）<textarea value={resolution} onChange={e => setResolution(e.target.value)} /></label>
      <p>每份案例须通过目标验收与审核；运行失败组需覆盖全部原始需求后才能标记解决。</p>
      <label>替代工具名（仅工具能力缺口需指定，可选）<input value={tool} onChange={e => setTool(e.target.value)} /></label>
      <button className="secondary-action" disabled={disabled || !note.trim()}>{resolution.trim() ? '核对证据并标记解决' : '保存分类，保持待解决'}</button>
    </form>
  </article>;
}
