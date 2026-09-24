import {AbsoluteFill, Img, interpolate, useCurrentFrame} from 'remotion';
import type {CaseRecord} from '../types';
import {viewAt} from '../data';
export type ObjectKind = 'input'|'output'|'state';
export function ExecutionScene({record,onObject}: {record:CaseRecord;onObject:(kind:ObjectKind)=>void}) {
  const frame=useCurrentFrame();
  const v=viewAt(record,frame);
  const flow=interpolate(v.local,[10,48],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const back=interpolate(v.local,[48,78],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  const title=v.current.values.layout.elements.find((e:any)=>e.id==='title');
  const facts=v.current.values.rendered_text_facts.find((e:any)=>e.element_id==='title');
  const resultSummary=[
    '恢复前后状态相等 · next: human_review',
    `round_number: ${v.before.values.round_number} → ${v.current.values.round_number}`,
    'title.font_size = 106（决策，尚未写入布局）',
    'title.font_size: 88 → 106 · 工具计数: 0 → 1',
    'decision: finish_round · 工具计数仍为 1',
    `实际标题字号: 88 → ${facts.actual_font_size}`,
    `目标检查: ${v.current.values.goal_verification?.outcome ?? '未采集'}`,
    `round_snapshots: ${v.before.values.round_snapshots.length} → ${v.current.values.round_snapshots.length} 项`,
    `waiting_for_human · ${v.current.values.layout_candidates.length} 个候选`,
  ];
  const card:React.CSSProperties={background:'#fff',border:'1px solid #d8e3e0',borderRadius:16,padding:'22px 24px',textAlign:'left',font:'inherit',color:'#193b35',cursor:'pointer'};
  return <AbsoluteFill style={{background:'#eff4f1',fontFamily:'"Microsoft YaHei",sans-serif',color:'#193b35',padding:40}}>
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
      <span style={{fontSize:17,letterSpacing:3,color:'#638278'}}>POSTERPILOT / EXECUTION</span>
      <span style={{fontSize:15,color:'#61736c'}}>测试替身执行 · 记录回放</span>
    </div>
    <div style={{fontSize:30,fontWeight:700,marginTop:22}}>{v.step?`${String(v.index+1).padStart(2,'0')}  ${v.step.title}`:'先看起点：这次从哪张海报开始'}</div>
    <div style={{fontSize:17,color:'#667c72',marginTop:8}}>{v.step?'节点边界有检查点证据；箭头与移动为教学示意':'用户意见：不要改变主视觉，只增强标题'}</div>
    <div style={{display:'grid',gridTemplateColumns:'1fr 242px',gap:28,marginTop:30,flex:1,minHeight:0}}>
      <div style={{display:'flex',flexDirection:'column',gap:14}}>
        <button onClick={()=>onObject('input')} style={card}>
          <span style={{fontSize:14,color:'#77857f'}}>输入 · 点击检查对象内容</span>
          <div style={{fontSize:22,marginTop:9}}>{v.step?.inputLabel??'已保存的任务状态'}</div>
        </button>
        <div style={{height:51,position:'relative',fontSize:16,paddingLeft:45,color:'#477eac'}}>
          <span style={{position:'absolute',left:20,top:0,height:48,borderLeft:'2px solid #7ea3c2'}}/>
          <span style={{position:'absolute',left:13,top:31*flow,fontSize:22}}>↓</span>
          <div style={{paddingTop:13}}>{v.step?'函数调用 · 传入上述参数':'恢复时按任务编号读取'}</div>
        </div>
        <div style={{...card,background:'#193f37',color:'#fff',border:0}}>
          <div style={{fontSize:14,opacity:.65}}>当前模块</div>
          <div style={{fontSize:v.index===8?18:22,marginTop:9,fontFamily:'Consolas,monospace',overflowWrap:'anywhere'}}>{v.step?.module??'SQLite checkpoint'}</div>
        </div>
        <div style={{height:47,position:'relative',fontSize:16,paddingLeft:45,color:'#9c7042',opacity:v.index<0?0:Math.max(.3,back)}}>
          <span style={{position:'absolute',left:20,top:0,height:42,borderLeft:'2px dashed #b48b5e'}}/>
          <span style={{position:'absolute',left:13,top:25*back,fontSize:22}}>↓</span>
          <div style={{paddingTop:9}}>数据返回 · {v.revealed?'已采集':'本步播放至返回阶段后显示'}</div>
        </div>
        <button disabled={!v.revealed && v.index>=0} onClick={()=>onObject('output')} style={{...card,opacity:v.revealed||v.index<0?1:.46}}>
          <div style={{fontSize:21}}>{v.index<0?'初始布局 · 标题 88':v.revealed?v.step!.outputLabel:'等待本步返回'}</div>
          {v.revealed&&<div style={{fontSize:15,color:'#74866e',marginTop:8}}>{resultSummary[v.index]}</div>}
        </button>
        <button onClick={()=>onObject('state')} style={{font:'inherit',textAlign:'left',border:0,background:'transparent',color:'#296f5b',fontSize:16,padding:'6px 3px',cursor:'pointer'}}>▣ 状态写入 · {v.revealed?`${v.changes.length} 个字段变化`:'显示修改前状态'} → 检查</button>
      </div>
      <div>
        <Img src={`/case/${v.poster}`} style={{width:242,height:323,objectFit:'contain',background:'#ddd5c7',boxShadow:'0 10px 25px #243d3520'}}/>
        <div style={{fontSize:15,marginTop:12,lineHeight:1.8}}>{v.poster==='poster_initial.png'?'初始产物 · 尚未生成修改版':'本轮正式产物 · 实际渲染'}<br/>布局字号 <b>{title.font_size}</b> / 已绘制 <b>{facts.actual_font_size}</b></div>
        <div style={{fontSize:14,color:'#728077',marginTop:12,lineHeight:1.7}}>这是测试产物。单色主视觉来自图片测试替身。</div>
      </div>
    </div>
    <div style={{fontSize:13,color:'#71837b',marginTop:15}}>蓝色实线：函数调用　棕色虚线：数据返回　绿色方块：状态写入　前端事件通知：未采集</div>
  </AbsoluteFill>;
}
