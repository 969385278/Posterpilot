import {useEffect,useMemo,useState} from 'react';
import {Player} from '@remotion/player';
import type {CaseRecord} from './types';
import {steps} from './content';
import {viewAt} from './data';
import {DURATION,FPS,stopFrame} from './timeline';
import {usePlayback} from './player/usePlayback';
import {ExecutionScene,type ObjectKind} from './animation/ExecutionScene';
import {Inspector,type Tab,JsonTree} from './components/Inspector';
import {Comparison} from './components/Comparison';
export default function App({record}:{record:CaseRecord}) {
  const p=usePlayback();
  const view=useMemo(()=>viewAt(record,p.frame),[record,p.frame]);
  const [tab,setTab]=useState<Tab>('source');
  const [selected,setSelected]=useState<{index:number;revealed:boolean;name:string}|null>(null);
  const [collapsed,setCollapsed]=useState(false);
  const [width,setWidth]=useState(420);
  const [why,setWhy]=useState(false);
  const selectedName=selected?.index===view.index&&selected.revealed===view.revealed?selected.name:null;
  useEffect(()=>{setWhy(false);setSelected(null);},[view.index]);
  const onObject=(kind:ObjectKind)=>{
    setTab(kind);setSelected({index:view.index,revealed:view.revealed,name:kind==='input'?(view.step?.inputLabel??'初始状态'):kind==='output'?(view.step?.outputLabel??'初始状态'):'状态快照'});
  };
  return <div className="app" style={{'--inspector-width':`${width}px`,'--nav-width':collapsed?'64px':'216px'} as React.CSSProperties} data-testid="app" data-frame={p.frame} data-step={view.step?.id??'intro'} data-playing={p.playing}>
    <header><div className="brand"><span className="brand-mark">P</span><div><b>PosterPilot</b><span>代码执行学习器</span></div></div><div className="header-meta"><span className="badge">使用测试替身的执行</span><span>CHAPTER 01</span><details className="evidence-popover"><summary>证据与边界</summary><div><b>当前源码 + 离线采集</b><p>{record.provenance}</p><p>版本：<code>{record.commit}</code><br/>采集：{record.capturedAt}<br/>业务源码修改：{record.businessSourceModified?'有':'无'}</p><ul>{record.limitations.map(x=><li key={x}>{x}</li>)}</ul><a href="/case/record.json" download="posterpilot-chapter-01.json">下载脱敏案例 JSON</a><p>仅下载记录，不执行业务任务。</p></div></details></div></header>
    <div className="workspace">
      <nav className="directory" aria-label="章节步骤"><div className="nav-heading"><span>{collapsed?'01':'第一章 · 一次修改'}</span><button aria-label={collapsed?'展开目录':'收起目录'} onClick={()=>setCollapsed(!collapsed)}>{collapsed?'›':'‹'}</button></div>{!collapsed&&<p className="nav-intro">从一句意见，到下一版海报。</p>}
        <button disabled={!!p.comparison} className={`step-button ${view.index<0?'active':''}`} onClick={()=>p.seek(0)} title="案例背景与初始状态"><span className="step-number">○</span>{!collapsed&&<span>案例起点<small>初始海报与证据范围</small></span>}</button>
        {steps.map((step,i)=><button disabled={!!p.comparison} aria-current={view.index===i?'step':undefined} className={`step-button ${view.index===i?'active':''}`} key={step.id} onClick={()=>p.seek(stopFrame(i))} title={step.title} data-testid={`step-${i}`}><span className="step-number">{String(i+1).padStart(2,'0')}</span>{!collapsed&&<span>{step.title}<small>{view.index===i?(view.complete?'讲解停帧':view.revealed?'结果已显示':'正在展开'):i<view.index?'已经过':'点击查看停帧'}</small></span>}</button>)}
        {!collapsed&&<div className="nav-footer">静态记录回放<br/>不会调用模型或执行任务</div>}
      </nav>
      <main>
        <div className="chapter-heading"><div><span className="eyebrow">不要改变主视觉，只增强标题</span><h1>{view.step?.title??'先看清修改的起点'}</h1></div><span className="position">{view.index<0?'准备开始':`${String(view.index+1).padStart(2,'0')} / 09`}</span></div>
        <div style={{display:p.comparison?'none':'block'}}>
          <div className="stage" data-testid="stage"><Player ref={p.player} component={ExecutionScene} inputProps={{record,onObject}} durationInFrames={DURATION} fps={FPS} compositionWidth={1000} compositionHeight={760} controls={false} clickToPlay={false} doubleClickToFullscreen={false} spaceKeyToPlayOrPause={false} autoPlay={false} loop={false} moveToBeginningWhenEnded={false} playbackRate={p.speed} style={{width:'100%'}}/></div>
          <section className="transport" aria-label="回放控制">
            <div className="transport-top"><div className="mode-switch"><button className={p.mode==='learn'?'selected':''} onClick={()=>p.setMode('learn')}>学习模式</button><button className={p.mode==='continuous'?'selected':''} onClick={()=>p.setMode('continuous')}>连续模式</button></div><label>倍速 <select aria-label="播放倍速" value={p.speed} onChange={e=>p.setSpeed(Number(e.target.value))}>{[.5,1,1.5,2,4].map(x=><option key={x} value={x}>{x}×</option>)}</select></label></div>
            <input className="progress" aria-label="教学进度" type="range" min="0" max={DURATION-1} value={p.frame} onPointerDown={p.pause} onChange={e=>p.seek(Number(e.target.value))} onPointerUp={p.pause}/>
            <div className="transport-bottom"><div className="buttons"><button onClick={p.previous} aria-label="上一步">← 上一步</button><button className="play" onClick={p.toggle} aria-label={p.playing?'暂停':'播放'}>{p.playing?'Ⅱ 暂停':'▶ 播放'}</button><button onClick={p.next} disabled={p.frame===DURATION-1} aria-label="下一步">下一步 →</button><button className="replay" onClick={p.replay}>↺ 重播本步</button></div><span className="frame-count">{p.frame} / {DURATION-1} 帧</span></div>
            <p className="transport-help">{p.mode==='learn'?'每个业务步骤结束后自动暂停。':'连续播放，不在教学停点自动暂停。'} 下一步与重播始终在该步结束后暂停。时间仅代表教学节奏。</p>
          </section>
          <section className="explanation" data-testid="explanation" data-step={view.step?.id??'intro'}>
            <div className="explanation-heading"><b>{view.index<0?'本次案例':view.revealed?'这一步做什么':'正在演示这一业务步骤'}</b><span className="badge subtle">{view.index<0?'实际初始状态':view.revealed?'完整讲解':'输入 → 调用 → 返回 → 写入'}</span></div>
            <p>{view.index<0?'初始海报来自当前仓库测试场景，标题已绘制为 88。用户意见是“不要改变主视觉，只增强标题”。初版生成不在本章内；点击“下一步”从恢复任务开始，逐步查看这条意见怎样改变布局和海报。':view.revealed?view.step!.what:'右侧已展示本步输入与源码；动画到达返回阶段后，输出、状态差异和完整讲解将一起显示。你可以随时暂停。'}</p>
            {view.index<0?<details><summary>展开真实初始状态摘要</summary><JsonTree value={{任务:record.initial.values.run_id,待执行节点:record.initial.next,布局:record.initial.values.layout,背景处理:record.initial.values.background_treatment,实际文字:record.initial.values.rendered_text_facts}}/></details>:<><div className="explain-actions"><button aria-expanded={why} onClick={()=>setWhy(!why)}>为什么这样设计 {why?'−':'＋'}</button><button onClick={p.enterComparison}>没有这项设计会怎样 ↗</button></div>{why&&<div className="why"><p>{view.step!.why}</p><p>{view.step!.cost}</p><small>设计解释依据当前源码与记录，不代表作者当时的真实动机。</small></div>}</>}
          </section>
        </div>
        {p.comparison&&<Comparison record={record} index={p.comparison.index} onExit={p.exitComparison}/>}
        <footer>空格播放 / 暂停 · ← → 切换步骤 · R 重播 · 选择文字或操作面板时快捷键不生效</footer>
      </main>
      <div className="inspector-wrap"><label className="resize-control">面板宽度 <input aria-label="检查面板宽度" type="range" min="320" max="650" value={width} onChange={e=>setWidth(Number(e.target.value))}/></label>{p.comparison?<aside className="inspector compare-aside"><h3>主线位置已保存</h3><p>第 {Math.max(1,p.comparison.index+1)} 步 · 第 {p.comparison.frame} 帧</p><p>当前是独立对照视图。主线代码与数据面板暂时收起，避免混用两条流程的数据。</p><button onClick={p.exitComparison}>返回主线</button></aside>:<Inspector record={record} view={view} tab={tab} setTab={next=>{setTab(next);setSelected(null);}} selected={selectedName}/>}</div>
    </div>
  </div>;
}
