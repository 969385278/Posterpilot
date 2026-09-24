import type {CaseRecord, State} from './types';
import {steps} from './content';
import {position} from './timeline';
export const MISSING = '未采集';
export const pick = (state: State, keys: string[]) => Object.fromEntries(keys.map(key => [key, key in state ? state[key] : MISSING]));
export const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
export function diff(before: any, after: any, path = ''): {path: string; before: any; after: any}[] {
  if (same(before, after)) return [];
  if (before !== null && after !== null && typeof before === 'object' && typeof after === 'object') {
    return [...new Set([...Object.keys(before), ...Object.keys(after)])].flatMap(key => diff(before[key], after[key], path ? `${path}.${key}` : key));
  }
  return [{path, before: before === undefined ? '字段不存在' : before, after: after === undefined ? '字段不存在' : after}];
}
export function viewAt(record: CaseRecord, frame: number) {
  const pos = position(frame);
  const {index, revealed} = pos;
  const snapshots = [record.restored, ...record.history];
  const before = index <= 0 ? record.initial : snapshots[index - 1];
  const after = index < 0 ? record.initial : snapshots[index];
  const current = revealed ? after : before;
  const step = index < 0 ? null : steps[index];
  let input: State = index < 0 ? {用户意见: record.decision, 起点: pick(record.initial.values, ['run_id','layout','main_visual_path','background_treatment']), 初始检查点: {next:record.initial.next, step:record.initial.step}} : pick(before.values, step!.fields);
  let output: State = index < 0 ? {说明:'初版生成不在本章内；这是实际保存的初始状态。'} : pick(after.values, step!.fields);
  if(index === 0) {
    input = {run_id: before.values.run_id, run_directory: before.values.run_directory, decision:record.decision, evidence:'采集程序关闭旧执行器，再打开同一 SQLite 文件。'};
    output = {恢复的状态:pick(after.values,step!.fields), next:after.next, 恢复前后状态相等:same(record.initial.values, record.restored.values)};
  }
  if(index === 1) input = {decision:record.decision, 之前状态:input};
  if(index === 2 || index === 4) {
    const call = record.providerCalls[index === 2 ? 1 : 2];
    input = {来源:`record.providerCalls[${index === 2 ? 1 : 2}].input`, 提供者:'DesignAndReactProvider（测试替身）', messages:call.input};
    output = {提供者原始响应:call.output, 写入状态:output};
  }
  if(index === 3) {
    input = {decision: before.values.react_decision, layout: before.values.layout, controls: before.values.design_controls, background_treatment:before.values.background_treatment};
    output = {...output, 校验结果:{工具轨迹:after.values.tool_traces, 内部逐项校验返回值:'未采集；成功 Observation 和返回布局已采集，内部调用关系依据源码。'}};
  }
  if(index === 5) {
    input = pick(before.values, ['layout','main_visual_path','background_treatment','round_number']);
    output = {...output, 背景证据:record.backgroundEvidence, 本轮渲染调用:record.renderCalls.filter(c => String(c.output?.path ?? '').endsWith('poster_round_1.png'))};
  }
  if(index === 6) input = pick(before.values,['poster_optimized_path','layout','rendered_text_facts','background_treatment']);
  if(index === 7) input = pick(before.values,['evaluation_initial','evaluation_optimized','poster_optimized_path','tool_traces','round_number','round_snapshots']);
  if(index === 8) {
    input = pick(before.values,['layout','evaluation_optimized','round_snapshots','design_controls']);
    output = {...output, 最终返回:record.outcome, 图中断:record.final.interrupts, 后续节点:record.final.next, 候选图片:'未采集（仅打包正式海报，候选元数据已采集）', 前端事件通知:record.missing.frontend_sse};
  }
  const fields = step?.fields ?? ['layout','background_treatment','main_visual_path'];
  const shownOutput = index < 0 || revealed ? output : {说明:'本步尚未执行到返回阶段。完成动画后显示已采集的输出。'};
  return {...pos, step, before, after, current, input, output:shownOutput,
    changes:revealed ? diff(before.values,after.values) : [],
    stateBefore:pick(before.values,fields), stateAfter:pick((revealed ? after : before).values,fields),
    poster:current.values.poster_optimized_path ? 'poster_round_1.png' : 'poster_initial.png',
    source: index < 0 ? 'record.initial' : index === 0 ? 'record.initial → record.restored' : `${index === 1 ? 'record.restored' : `record.history[${index-2}]`} → record.history[${index-1}]`,
  };
}
export type View = ReturnType<typeof viewAt>;
