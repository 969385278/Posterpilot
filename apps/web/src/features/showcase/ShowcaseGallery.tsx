import { useState } from 'react';
import showcase from '../../data/showcase.json';
import '../../styles/showcase.css';

export function ShowcaseGallery() {
  const [selected, setSelected] = useState(showcase.entries[0].id);
  const entry = showcase.entries.find(item => item.id === selected)!;
  const failed = entry.goal_verification.checks.filter(check => check.status === 'failed');
  return <section className="showcase" aria-labelledby="showcase-title">
    <h2 id="showcase-title">看一次真实的排版调整</h2>
    <p className="showcase-notice">公共领域背景，项目实际渲染；使用固定演示决策，非生图模型输出。活动均为虚构，未收集用户反馈。</p>
    <div className="showcase-switch" aria-label="选择展示场景">
      {showcase.entries.map(item => <button type="button" className="secondary-action" key={item.id}
        aria-pressed={item.id === selected} onClick={() => setSelected(item.id)}>{item.label}</button>)}
    </div>
    <div className="showcase-content">
      <div className="showcase-images">
        <figure><img src={entry.images.initial} alt={`${entry.title}初版`} width="1080" height="1440" loading="lazy" /><figcaption>初版</figcaption></figure>
        <figure><img src={entry.images.optimized} alt={`${entry.title}调整后`} width="1080" height="1440" loading="lazy" /><figcaption>调整后：放大时间地点</figcaption></figure>
      </div>
      <div className="showcase-detail" aria-live="polite">
        <h3>{entry.title}</h3>
        <p>{entry.lesson}</p>
        <p><strong>{entry.quality_issues.length ? '待改进，不进入成功经验库' : '当前检查通过，可作为排版参考'}</strong></p>
        <p>{entry.quality_issues.length ? '文字已放大，但部分区域的背景对比仍不足。工具执行成功，不等于所有目标达成。' : '未发现本次检查覆盖范围内的阻断问题，不代表审美、注意力或用户满意度提升。'}</p>
        {failed.length > 0 && <details><summary>查看未通过的检查（{failed.length}）</summary>
          <ul>{failed.map((check, index) => <li key={index}>{check.detail}</li>)}</ul>
        </details>}
        <details><summary>素材来源与使用边界</summary>
          <p>{entry.source.creator}</p>
          <p>{entry.source.rights}。展示中进行了竖版裁切与中文排版，非原作完整构图。</p>
          <p>{entry.avoid_when}</p>
          <a href={entry.source.source_url} target="_blank" rel="noreferrer">查看原图与许可</a>
        </details>
        <a className="text-action" href="/showcase/index.json" target="_blank" rel="noreferrer">查看实际执行与评测记录</a>
      </div>
    </div>
  </section>;
}
