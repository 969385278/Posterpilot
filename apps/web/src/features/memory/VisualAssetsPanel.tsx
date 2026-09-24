import { useEffect, useState, type FormEvent } from 'react';

type Metadata = { title: string; description: string; styles: string[]; scenarios: string[]; visible_text: string; composition: string; cautions: string };
type Source = { origin: string; creator: string; source_url: string | null; rights: string; original_sha256?: string };
type Asset = { id: string; revision: number; status: string; metadata: Metadata; sources: Source[]; image_sha256: string; measured: { width: number; height: number; palette: { color: string; fraction: number }[] }; near_duplicates: { id: string; distance: number }[]; enrichment: { proposal: Metadata; basis: string } | null; audit: { action: string; revision: number; note?: string; reviewer?: string }[] };
type SearchResult = { mode: string; fallback_reason: string | null; matches: { asset_id: string; revision: number; title: string; score: number; reason: { lexical_overlap: number; cosine: number | null } }[] };
const base = '/api/v1/datahub/visual-assets';
const empty: Metadata = { title: '', description: '', styles: [], scenarios: ['cultural_event'], visible_text: '', composition: '', cautions: '' };
const statuses: Record<string, string> = { candidate: '待审核', approved: '可供引用', withdrawn: '已撤回', rejected: '已驳回' };
const scenarios = { campus_lecture: '校园讲座', cultural_event: '文化活动', club_recruitment: '社团招新' };

async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(base + path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error?.message || (typeof value.detail === 'string' ? value.detail : '素材操作失败，请检查必填项或服务配置'));
  return value;
}

function MetadataFields({ value, onChange }: { value: Metadata; onChange: (value: Metadata) => void }) {
  const [styleText, setStyleText] = useState(value.styles.join(','));
  const [lastStyles, setLastStyles] = useState(value.styles);
  if (value.styles !== lastStyles) {
    setLastStyles(value.styles);
    if (styleText.split(/[,，]/).map(s => s.trim()).filter(Boolean).join(',') !== value.styles.join(',')) setStyleText(value.styles.join(','));
  }
  function update(key: keyof Metadata, content: string | string[]) { onChange({ ...value, [key]: content }); }
  return <>
    <label>素材标题<input required maxLength={200} value={value.title} onChange={e => update('title', e.target.value)} /></label>
    <label>画面描述<textarea maxLength={2000} value={value.description} onChange={e => update('description', e.target.value)} /></label>
    <label>风格标签（逗号分隔）<input value={styleText} onChange={e => { setStyleText(e.target.value); update('styles', e.target.value.split(/[,，]/).map(s => s.trim()).filter(Boolean)); }} /></label>
    <fieldset><legend>适用场景</legend>{Object.entries(scenarios).map(([key, label]) => <label key={key} className="inline-checkbox"><input type="checkbox" checked={value.scenarios.includes(key)} onChange={e => update('scenarios', e.target.checked ? [...value.scenarios, key] : value.scenarios.filter(s => s !== key))} />{label}</label>)}</fieldset>
    <label>可辨认文字<textarea maxLength={2000} value={value.visible_text} onChange={e => update('visible_text', e.target.value)} /></label>
    <label>构图描述<textarea maxLength={2000} value={value.composition} onChange={e => update('composition', e.target.value)} /></label>
    <label>使用限制与不确定性<textarea maxLength={2000} value={value.cautions} onChange={e => update('cautions', e.target.value)} /></label>
  </>;
}

export function VisualAssetsPanel() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [reload, setReload] = useState(0);
  const [metadata, setMetadata] = useState<Metadata>({ ...empty });
  const [source, setSource] = useState<Source>({ origin: 'original', creator: '', source_url: null, rights: '' });
  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [query, setQuery] = useState('');
  const [scenario, setScenario] = useState('');
  const [result, setResult] = useState<SearchResult | null>(null);
  useEffect(() => {
    let active = true;
    call<Asset[]>('').then(value => { if (active) setAssets(value); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [reload]);
  async function act(operation: () => Promise<void>) {
    setBusy(true); setError(''); setNotice(''); setResult(null);
    try { await operation(); setReload(x => x + 1); }
    catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    await act(async () => {
      if (file.size > 10_000_000) throw new Error('图片最多 10 MB');
      const encoded = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1]);
        reader.onerror = () => reject(new Error('无法读取图片'));
        reader.readAsDataURL(file);
      });
      const saved = await call<{ asset: Asset; duplicate: boolean }>('', { image_base64: encoded, metadata, source });
      setSelected(saved.asset.id);
      setNotice(saved.duplicate ? '检测到相同像素，已返回已有素材；新增来源需要重新审核。' : '素材已入库，主色与尺寸已提取；审核前不会被 Agent 使用。');
    });
  }
  const item = assets.find(asset => asset.id === selected);
  return <section className="hub-lab" aria-label="视觉素材管理">
    <h2>有来源、可审核的视觉参考</h2><p>上传静态图片，补全描述与使用权。模型只给候选分析，审核通过后才进入问答和生成参考。语义检索针对已审核描述，不是图片向量。</p>
    <details><summary>上传一张素材</summary><form className="hub-editor" onSubmit={e => void upload(e)}>
      <label>图片（PNG、JPEG、WebP，最多 10 MB）<input required type="file" accept="image/png,image/jpeg,image/webp" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
      <MetadataFields value={metadata} onChange={setMetadata} />
      <label>素材来源<select value={source.origin} onChange={e => setSource({ ...source, origin: e.target.value })}><option value="original">本人原创或提供</option><option value="external">外部素材</option></select></label>
      <label>作者或提供者<input required maxLength={200} value={source.creator} onChange={e => setSource({ ...source, creator: e.target.value })} /></label>
      <label>来源链接<input type="url" required={source.origin === 'external'} value={source.source_url ?? ''} onChange={e => setSource({ ...source, source_url: e.target.value || null })} /></label>
      <label>使用权与署名要求<textarea required maxLength={1000} value={source.rights} onChange={e => setSource({ ...source, rights: e.target.value })} /></label>
      <button className="primary-action" disabled={busy || !file}>上传并检查重复</button>
    </form></details>
    <form className="hub-filters" onSubmit={e => { e.preventDefault(); void act(async () => setResult(await call<SearchResult>('/search', { query, scenario: scenario || null, limit: 5 }))); }}>
      <label>检索需求<input required maxLength={1000} value={query} onChange={e => setQuery(e.target.value)} /></label>
      <label>检索场景<select value={scenario} onChange={e => setScenario(e.target.value)}><option value="">所有场景</option>{Object.entries(scenarios).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <button className="secondary-action" disabled={busy || !query.trim()}>检索已审核素材</button>
      <button type="button" className="secondary-action" disabled={busy} onClick={() => void act(async () => { const value = await call<{ indexed: number; eligible: number }>('/index', {}); setNotice(`已为 ${value.indexed}/${value.eligible} 张审核素材建立语义索引。`); })}>更新语义索引</button>
    </form>
    {result && <section aria-label="素材检索结果"><p>{result.mode === 'hybrid' ? '语义与词法混合检索' : '词法检索'} · {result.fallback_reason || '当前索引可用'}</p>{!result.matches.length && <p>没有匹配的已审核素材。</p>}{result.matches.map(match => <p key={match.asset_id}><button className="text-action" onClick={() => setSelected(match.asset_id)}>{match.title} · v{match.revision}</button> · 词法重合 {match.reason.lexical_overlap.toFixed(2)} · 语义余弦 {match.reason.cosine?.toFixed(2) ?? '不可用'}</p>)}</section>}
    <div className="hub-catalog">{assets.map(asset => <article className="hub-card" key={asset.id}><button className="hub-card-open" onClick={() => setSelected(asset.id)}><img src={`${base}/${asset.id}/image`} alt={asset.metadata.title} loading="lazy" /><div><h3>{asset.metadata.title}</h3><p>{statuses[asset.status]} · v{asset.revision}</p><p>{asset.measured.width} × {asset.measured.height} · {asset.near_duplicates.length ? `${asset.near_duplicates.length} 张可能相似（需人工判断）` : '未发现近似哈希'}</p></div></button></article>)}</div>
    {!assets.length && <p>素材库为空。上传后可检查特征、来源并审核。</p>}
    {item && <AssetEditor key={`${item.id}:${item.revision}`} item={item} busy={busy} act={act} />}
    {notice && <p role="status">{notice}</p>}{error && <p role="alert" className="inline-error">{error}</p>}
  </section>;
}

function AssetEditor({ item, busy, act }: { item: Asset; busy: boolean; act: (operation: () => Promise<void>) => Promise<void> }) {
  const [metadata, setMetadata] = useState(item.metadata);
  const [reviewer, setReviewer] = useState('');
  const [note, setNote] = useState('');
  const [rights, setRights] = useState(false);
  const dirty = JSON.stringify(metadata) !== JSON.stringify(item.metadata);
  async function review(action: string) { await act(async () => { await call(`/${item.id}/review`, { expected_revision: item.revision, action, reviewer, note, rights_confirmed: rights }); }); }
  return <section className="hub-detail" aria-label="素材详情"><h3>{item.metadata.title} · {statuses[item.status]} · v{item.revision}</h3>
    <p>主色（白底合成像素统计）：{item.measured.palette.map(color => `${color.color} ${(color.fraction * 100).toFixed(0)}%`).join(' / ')}</p>
    <h4>来源与使用权</h4>{item.sources.map((source, index) => <p key={index}>{source.creator} · {source.source_url ? <a href={source.source_url} target="_blank" rel="noreferrer">来源页面</a> : '提供者声明原创'} · {source.rights}</p>)}
    <p>内容 SHA256：{item.image_sha256}</p>
    <button className="secondary-action" disabled={busy || dirty} onClick={() => void act(async () => { await call(`/${item.id}/enrich`, { expected_revision: item.revision }); })}>用视觉模型补全候选特征</button>
    {item.enrichment && <details><summary>查看模型候选（未自动采纳）</summary><pre>{JSON.stringify(item.enrichment.proposal, null, 2)}</pre><button className="secondary-action" disabled={busy} onClick={() => setMetadata(item.enrichment!.proposal)}>将候选填入编辑区</button></details>}
    <form className="hub-editor" onSubmit={e => { e.preventDefault(); void act(async () => { await call(`/${item.id}/edit`, { expected_revision: item.revision, metadata }); }); }}><MetadataFields value={metadata} onChange={setMetadata} /><button className="secondary-action" disabled={busy || !dirty}>保存资料并重新审核</button></form>
    <div className="hub-editor"><label>素材审查人<input maxLength={80} value={reviewer} onChange={e => setReviewer(e.target.value)} /></label><label>素材审查说明<textarea maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label><label className="inline-checkbox"><input type="checkbox" checked={rights} onChange={e => setRights(e.target.checked)} />已核对所有来源的使用权、描述及适用范围</label>
      <div className="hub-actions"><button className="primary-action" disabled={busy || dirty || !rights || !reviewer.trim() || !note.trim()} onClick={() => void review('approve')}>审核并允许引用</button><button className="secondary-action" disabled={busy || dirty || !reviewer.trim() || !note.trim()} onClick={() => void review('withdraw')}>撤回素材</button></div>
    </div><details><summary>素材修订记录</summary>{item.audit.map((entry, i) => <p key={i}>v{entry.revision} · {entry.action} · {entry.reviewer} {entry.note}</p>)}</details>
  </section>;
}
