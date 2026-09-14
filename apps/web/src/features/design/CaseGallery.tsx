import { useEffect, useState } from 'react';
import { aspectLabels, caseImageUrl, listPosterCases, selectReferenceAspect, type PosterCase, type ReferenceAspect, type ReferenceSelection } from '../../api/design';

type Props = { value: ReferenceSelection[]; onChange: (value: ReferenceSelection[]) => void; disabled?: boolean };

export function CaseGallery({ value, onChange, disabled }: Props) {
  const [cases, setCases] = useState<PosterCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [style, setStyle] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    void listPosterCases(controller.signal).then(items => { if (!controller.signal.aborted) setCases(items); })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '读取案例失败。'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);
  const normalized = query.trim().toLocaleLowerCase();
  const visible = cases.filter(item => (!style || item.styles.includes(style)) && (!normalized || [item.title, item.original_title, ...item.styles, ...item.scenarios, ...Object.values(item.features)].join(' ').toLocaleLowerCase().includes(normalized)));
  const styles = [...new Set(cases.flatMap(item => item.styles))];
  function choose(caseId: string, aspect: ReferenceAspect, checked: boolean) {
    try { onChange(selectReferenceAspect(value, caseId, aspect, checked)); setError(''); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '无法应用选择。'); }
  }
  return <section className="case-gallery" aria-label="海报案例 Wiki">
    <h2>先看看喜欢的设计</h2>
    <p className="design-help">可选。只参考你勾选的特点，不复制原海报文字。每个维度选择一个来源，最多参考三张。</p>
    {value.length > 0 && <div className="reference-summary" aria-label="已选参考">
      {value.map(selection => <p key={selection.case_id}>{cases.find(item => item.id === selection.case_id)?.title ?? selection.case_id}：{selection.aspects.map(aspect => aspectLabels[aspect]).join('、')}
        <button type="button" className="text-action" disabled={disabled} onClick={() => onChange(value.filter(item => item.case_id !== selection.case_id))}>取消该参考</button>
      </p>)}
    </div>}
    {loading ? <p role="status">正在读取案例…</p> : error && !cases.length ? <div><p role="alert">{error}</p><button type="button" className="secondary-action" onClick={() => setRetry(count => count + 1)}>重新读取案例</button></div> : !cases.length ? <p>案例库暂无已整理素材，可以先直接生成海报。</p> : <>
      <div className="case-filters">
        <label>搜索案例<input value={query} onChange={event => setQuery(event.target.value)} placeholder="如：留白、复古、强对比" /></label>
        <label>风格筛选<select value={style} onChange={event => setStyle(event.target.value)}><option value="">全部风格</option>{styles.map(item => <option key={item}>{item}</option>)}</select></label>
      </div>
      {error && <p role="alert" className="inline-error">{error}</p>}
      {!visible.length && <p>没有匹配的案例，试试其他关键词。</p>}
      <div className="case-grid">{visible.map(item => <article className="case-card" key={item.id}>
        <button type="button" className="case-open" aria-expanded={expanded === item.id} onClick={() => setExpanded(expanded === item.id ? null : item.id)}>
          <img src={caseImageUrl(item.id)} alt={`${item.title}参考海报`} loading="lazy" />
          <strong>{item.title}</strong><span>{item.styles.join(' / ')}</span>
          <span className="design-help">{expanded === item.id ? '收起特点' : '查看特点并选择'}</span>
        </button>
        {expanded === item.id && <div className="case-detail">
          <p>{item.original_title}</p>
          <div className="palette-swatches" aria-label="参考配色">{item.palette.map(color => <span key={color} style={{ backgroundColor: color }} title={color} />)}</div>
          {(Object.keys(aspectLabels) as ReferenceAspect[]).map(aspect => <label className="case-aspect" key={aspect}>
            <input type="checkbox" disabled={disabled} checked={Boolean(value.find(selection => selection.case_id === item.id)?.aspects.includes(aspect))} onChange={event => choose(item.id, aspect, event.target.checked)} />
            <span><strong>参考{aspectLabels[aspect]}</strong><small>{item.features[aspect]}</small></span>
          </label>)}
          <p className="design-help">适用：{item.scenarios.join('、')}。案例分析是参考意见，不是设计规范或精确字体识别。</p>
          <p className="design-help">所选字体气质和文字构图会映射为少量可用中文字体/布局预设，不复刻原字体、旋转文字或图像图层。</p>
          {item.cautions.map(note => <p className="design-help" key={note}>{note}</p>)}
          <details><summary>来源与使用说明</summary><p>{item.source.creator}<br />{item.source.institution}</p><a href={item.source.source_url} target="_blank" rel="noreferrer">查看原始来源</a><p>{item.source.rights} <a href={item.source.rights_url} target="_blank" rel="noreferrer">权利说明</a></p><p>开发方已整理，等待你最终验收。</p></details>
        </div>}
      </article>)}</div>
    </>}
  </section>;
}
