import {steps} from '../content';
import type {CaseRecord} from '../types';
import {Copy,JsonTree,SourceCode} from './Inspector';
export function Comparison({record,index,onExit}:{record:CaseRecord;index:number;onExit:()=>void}) {
  const step=steps[index];
  const c=record.counterfactual;
  const measured=step?.id==='execute-tool';
  return <section className="comparison" data-testid="comparison">
    <div className="compare-heading"><div><span className="eyebrow">独立对照 · 主线已暂停</span><h2>{measured?'去掉第一层校验，会发生什么？':`${step?.title??'恢复任务'}：缺少这项设计时`}</h2></div><button onClick={onExit}>返回原学习位置</button></div>
    {!measured?<><p className="badge amber">基于源码的推断 · 未运行这个反例</p><p>{step?.without??steps[0].without}</p><p>{step?.cost??steps[0].cost}</p></>:<>
      <p className="badge amber">已执行的隔离测试 · 使用测试替身的执行</p>
      <p>两次都传入同一份初始布局和字号 999；只在隔离函数副本中删除第一处 <code>validate_actions(actions, layout)</code>。原业务文件和正式函数保持原样。</p>
      <details><summary>相同输入：title.font_size = 999</summary><Copy value={c.input}/><JsonTree value={c.input}/></details>
      <div className="compare-grid">{(['normal','without_first_guard'] as const).map((key,i)=><article key={key}><h3>{i===0?'原始函数':'仅移除第一层校验'}</h3><p className="rejected">均被拒绝</p><b>{c.results[key].error.type}</b><pre>{c.results[key].error.message}</pre><p>调用方布局保持不变，标题仍为 88。没有返回新布局，也没有渲染海报。</p><details><summary>查看已保存的完整测试结果</summary><Copy value={c.results[key]}/><JsonTree value={c.results[key]}/></details></article>)}</div>
      <p className="conclusion">{c.conclusion}</p>
      <p>这说明第一层不是此输入的唯一防线。它可以更早给出动作层面的错误，但这一个实验不足以证明两层规则对所有输入都等价。真实系统需要维护重复规则的一致性。</p>
      <details><summary>查看仍然拦截的源码证据</summary><SourceCode source={record.sources.find(s=>s.symbol==='apply_optimization_actions')!} ranges={[[23,23],[32,32],[61,61]]}/><SourceCode source={record.sources.find(s=>s.symbol==='LayoutElement')!} ranges={[[40,40]]}/></details>
    </>}
    <p className="muted">按业务步骤对应到「{step?.title??'恢复原任务'}」，不比较两条时间轴的秒数。返回后保持暂停，恢复进入对照前的精确帧位置。</p>
  </section>;
}
