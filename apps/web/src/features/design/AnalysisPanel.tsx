import { traitLabels, type GoalVerification, type PosterAnalysis, type TraitKey, type VerificationCheck } from '../../api/design';

const basisLabels = { image_measurement: '图像实测', render_metadata: '实际渲染参数', model_judgment: '模型意见' };
const statusLabels = { passed: '通过', failed: '未满足', unavailable: '无法验证' };

export function CheckList({ checks }: { checks: VerificationCheck[] }) {
  return <ul className="verification-checks">{checks.map(check => <li key={check.key}>
    <div><strong>{traitLabels[check.label as TraitKey] ?? check.label}</strong><span className={`check-status check-${check.status}`}>{statusLabels[check.status]}</span></div>
    {check.before != null && check.after != null && <small>{check.before.toFixed(3)} → {check.after.toFixed(3)}</small>}
    <p>{check.detail}</p>
  </li>)}</ul>;
}

export function VerificationPanel({ verification }: { verification?: GoalVerification | null }) {
  if (!verification) return null;
  return <section className="goal-verification" aria-label="本轮目标验证"><h3>本轮是否按要求修改？</h3><p>{verification.summary}</p><details><summary>查看逐项检查</summary><CheckList checks={verification.checks} /></details></section>;
}

export function AnalysisPanel({ analysis }: { analysis?: PosterAnalysis | null }) {
  if (!analysis) return null;
  function exportAnalysis() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(analysis, null, 2)], { type: 'application/json;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'poster-design-analysis.json'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <details className="design-analysis"><summary>查看这版海报的设计特点</summary>
    <div className="analysis-content">
      <div className="palette-swatches" aria-label="背景主要颜色">{analysis.palette.map(color => <span key={color} style={{ backgroundColor: color }} title={color} />)}</div>
      <dl className="feature-facts">{analysis.features.map(feature => <div key={feature.key}><dt>{feature.label}</dt><dd>{feature.value == null ? '暂无数据' : feature.value.toFixed(3)}<small>{feature.unit} / {basisLabels[feature.basis]}</small><p>{feature.explanation}</p></dd></div>)}</dl>
      <details><summary>实际使用的字体与字号</summary>{analysis.text_facts.map(fact => <p key={fact.element_id}><strong>{fact.content}</strong><br />{fact.font_name}，实际 {fact.actual_font_size}px（请求 {fact.requested_font_size}px），{fact.line_count} 行。{fact.fits_box ? '位于分配区域内。' : '超出分配区域。'}</p>)}</details>
      {analysis.visual_summary && <p><strong>视觉模型意见：</strong>{analysis.visual_summary}</p>}
      <details><summary>可读性检查与分析边界</summary><CheckList checks={analysis.readability_checks} />{analysis.warnings.map(note => <p key={note} className="design-help">{note}</p>)}</details>
      <button type="button" className="text-action" onClick={exportAnalysis}>导出特点分析 JSON</button>
    </div>
  </details>;
}
