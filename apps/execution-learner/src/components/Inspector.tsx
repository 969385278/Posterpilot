import {useState} from 'react';
import type {CaseRecord, Source} from '../types';
import type {View} from '../data';
import {same} from '../data';
export type Tab = 'source'|'input'|'output'|'state';
export function Copy({value,label='复制'}:{value:unknown;label?:string}) {
  const [message,setMessage]=useState(label);
  return <button className="small" onClick={async()=>{
    try {await navigator.clipboard.writeText(typeof value==='string'?value:JSON.stringify(value,null,2));setMessage('已复制');}
    catch {setMessage('请选中文字复制');}
  }}>{message}</button>;
}
export function JsonTree({value,label='对象',depth=0}:{value:any;label?:string;depth?:number}) {
  if(value===null || typeof value!=='object') return <div className="json-leaf"><span>{label}: </span><code>{value===null?'null':String(value)}</code></div>;
  const entries=Object.entries(value);
  return <details className="json-tree" open={depth<1}><summary>{label} <span>{Array.isArray(value)?`[${entries.length} 项]`:`{${entries.length} 字段}`}</span></summary><div>{entries.length?entries.map(([key,child])=><JsonTree key={key} value={child} label={key} depth={depth+1}/>):<code>空{Array.isArray(value)?'列表':'对象'}</code>}</div></details>;
}
export function SourceCode({source,ranges=[]}:{source:Source;ranges?:[number,number][]}) {
  return <><div className="source-meta"><b>{source.symbol}</b><span>{source.path}:{source.start}–{source.end}</span><Copy value={source.code} label="复制源码"/></div>
    <pre className="source-code" tabIndex={0}>{source.code.split('\n').map((line,index)=>{
      const num=source.start+index;return <div key={num} className={ranges.some(([a,b])=>num>=a&&num<=b)?'highlight':''}><span className="line-number">{num}</span><code>{line||' '}</code></div>;
    })}</pre><details className="hash"><summary>代码文件 SHA-256</summary><code>{source.sha256}</code></details></>;
}
export function Inspector({record,view,tab,setTab,selected}:{record:CaseRecord;view:View;tab:Tab;setTab:(tab:Tab)=>void;selected:string|null}) {
  const symbols=view.step?.symbols??['LangGraphAgentExecutor.resume','LangGraphAgentExecutor._config'];
  const sources=symbols.map(symbol=>record.sources.find(s=>s.symbol===symbol)!);
  const [sourceId,setSourceId]=useState('');
  const source=sources.find(s=>s.id===sourceId)??sources[0];
  const data=tab==='input'?view.input:view.output;
  const changes=view.changes.filter(d=>view.step?.fields.some(key=>d.path===key||d.path.startsWith(key+'.')));
  return <aside className="inspector" data-inspector data-testid="inspector" data-step={view.step?.id??'intro'} data-revealed={view.revealed}>
    <div className="panel-heading"><span>检查面板</span><small>{view.index<0?'初始状态':`${view.index+1} / 9`}</small></div>
    <div className="tabs" role="tablist" aria-label="检查内容">{([['source','源码'],['input','输入'],['output','输出'],['state','状态变化']] as const).map(([key,name])=><button key={key} role="tab" aria-selected={tab===key} onClick={()=>setTab(key)}>{name}</button>)}</div>
    <div className="inspector-scroll" key={`${view.index}-${tab}`}>
      <p className="evidence">使用测试替身的执行<br/><span>{view.source}</span></p>
      {selected&&<p className="object-note">已选择：{selected} · 当前步骤采集对象</p>}
      {tab==='source'&&<><label className="field-label">本步涉及的函数<select aria-label="源码函数" value={source.id} onChange={e=>setSourceId(e.target.value)}>{sources.map(s=><option value={s.id} key={s.id}>{s.symbol}</option>)}</select></label><SourceCode source={source} ranges={view.step?.highlights[source.symbol]??[[71,85]]}/><details className="pseudocode"><summary>用初级写法理解（教学伪代码）</summary><pre>{view.step?.pseudo??'状态 = 读取检查点(任务编号)\n显示初始海报和布局'}</pre><p>帮助理解，不是实际运行的 Python 源码。</p></details></>}
      {(tab==='input'||tab==='output')&&<><div className="data-toolbar"><b>{tab==='input'?'本步输入':'本步输出'}</b><Copy value={data} label="复制 JSON"/></div><JsonTree value={data}/><details><summary>展开为完整 JSON 文本</summary><pre className="raw-json" tabIndex={0}>{JSON.stringify(data,null,2)}</pre></details></>}
      {tab==='state'&&<>
        <p className="muted">{view.index<0?'这是修改开始前的状态。':view.revealed?'只突出本步确实改变的字段。数组下标从 0 开始。':'本步尚未写入；下方展示修改前状态。'}</p>
        {view.revealed&&<div data-testid="state-diff">{changes.length?changes.map(d=><div className="diff" key={d.path}><b>{d.path}</b><div className="before"><span>修改前</span><JsonTree value={d.before} label="值"/></div><div className="after"><span>修改后</span><JsonTree value={d.after} label="值"/></div></div>):<p className="unchanged">本步业务字段保持不变。</p>}</div>}
        {['main_visual_path','background_treatment'].map(k=>same(view.before.values[k],view.current.values[k])&&<div className="unchanged" key={k}>{k} <b>保持不变</b></div>)}
        <details><summary>本步字段快照：修改前 → 当前</summary><Copy value={{before:view.stateBefore,after:view.stateAfter}} label="复制快照"/><JsonTree label="修改前" value={view.stateBefore}/><JsonTree label="当前" value={view.stateAfter}/></details>
        {view.revealed&&<details><summary>全部状态变化（含事件记录）</summary><Copy value={view.changes} label="复制全部变化"/><JsonTree value={view.changes}/></details>}
      </>}
      <div className="artifact-link"><a href={`/case/${view.poster}`} target="_blank" rel="noreferrer">打开当前已生成的海报原图 ↗</a><span>只读取已保存图片</span></div>
      <div className="boundary">节点边界和字段值来自保存记录；函数内部顺序依据冻结源码。逐行变量、真实运行耗时、前端通知：未采集。</div>
    </div>
  </aside>;
}
