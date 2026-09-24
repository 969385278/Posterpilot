import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {DURATION,STEP_COUNT,position,startFrame,stopFrame,nextStop,nextIndex,previousFrame,crossedStop} from '../src/timeline';
import {steps} from '../src/content';
import {viewAt,same} from '../src/data';
import type {CaseRecord} from '../src/types';
const record:CaseRecord=JSON.parse(readFileSync(new URL('../public/case/record.json',import.meta.url),'utf8'));
test('nine stable business steps cover every frame without overlaps',()=>{
  assert.equal(steps.length,STEP_COUNT);assert.equal(new Set(steps.map(s=>s.id)).size,STEP_COUNT);
  assert.equal(position(0).index,-1);
  for(let i=0;i<9;i++){assert.equal(position(startFrame(i)).index,i);assert.equal(position(stopFrame(i)).index,i);assert.equal(position(stopFrame(i)).complete,true);}
  assert.equal(stopFrame(8),DURATION-1);
});
test('next and previous use business boundaries; the same stop never re-arms',()=>{
  assert.equal(nextIndex(0),0);assert.equal(nextStop(0),stopFrame(0));assert.equal(nextStop(stopFrame(0)),stopFrame(1));
  assert.equal(previousFrame(startFrame(4)+20),stopFrame(3));assert.equal(previousFrame(stopFrame(0)),0);
  assert.equal(nextStop(DURATION-1),null);
});
test('skipped stop is detected at high playback speed',()=>{
  assert.equal(crossedStop(148,149),false);assert.equal(crossedStop(149,149),true);assert.equal(crossedStop(153,149),true);assert.equal(crossedStop(200,null),false);
});
test('direct jumps and rewinds derive all output from the target frame',()=>{
  const final=viewAt(record,stopFrame(8));assert.equal(final.poster,'poster_round_1.png');
  const toolStart=viewAt(record,startFrame(3));assert.equal(toolStart.current.values.layout.elements[0].font_size,88);assert.equal(toolStart.poster,'poster_initial.png');assert.equal(toolStart.changes.length,0);assert.match(JSON.stringify(toolStart.output),/尚未/);
  const toolStop=viewAt(record,stopFrame(3));assert.equal(toolStop.current.values.layout.elements[0].font_size,106);assert.equal(toolStop.poster,'poster_initial.png');assert.equal(toolStop.current.values.rendered_text_facts[0].actual_font_size,88);
  const renderStart=viewAt(record,startFrame(5));assert.equal(renderStart.poster,'poster_initial.png');
  const renderEnd=viewAt(record,stopFrame(5));assert.equal(renderEnd.poster,'poster_round_1.png');assert.equal(renderEnd.current.values.rendered_text_facts[0].actual_font_size,106);
  assert.deepEqual(viewAt(record,0).current,record.initial);
});
test('each step references a real captured source and valid highlight ranges',()=>{
  for(const step of steps)for(const symbol of step.symbols){const s=record.sources.find(x=>x.symbol===symbol);assert.ok(s,symbol);for(const[a,b]of step.highlights[symbol]??[])assert.ok(a>=s.start&&b<=s.end&&a<=b,`${symbol}:${a}-${b}`);}
});
test('source snapshots match current unchanged business and fixture files',()=>{
  for(const s of record.sources){const path=fileURLToPath(new URL(`../../../${s.path}`,import.meta.url));const bytes=readFileSync(path);assert.equal(createHash('sha256').update(bytes).digest('hex'),s.sha256,s.path);const lines=bytes.toString('utf8').split(/\r?\n/).slice(s.start-1,s.end).join('\n');assert.equal(lines.trimEnd(),s.code.trimEnd(),s.symbol);}
});
test('assets are captured bytes and main visual was reused',()=>{
  for(const a of record.assets)assert.equal(createHash('sha256').update(readFileSync(new URL(`../public/case/${a.file}`,import.meta.url))).digest('hex'),a.sha256);
  assert.equal(record.backgroundEvidence.beforeSha256,record.backgroundEvidence.afterSha256);assert.equal(record.backgroundEvidence.imageCallsBefore,1);assert.equal(record.backgroundEvidence.imageCallsAfter,1);
  assert.ok(same(record.initial.values.background_treatment,record.final.values.background_treatment));
});
test('restoration, observed tool order and outcome are grounded in snapshots',()=>{
  assert.deepEqual(record.initial.values,record.restored.values);
  assert.deepEqual(record.history.map(s=>s.next[0]),['react_decide','execute_react_tool','react_decide','render_round','evaluate_round','complete_round','propose_layout_candidates','human_review']);
  assert.deepEqual(record.final.values.tool_traces.map((t:any)=>t.tool_name),['modify_typography']);assert.equal(record.outcome.status,'waiting_for_human');
});
test('counterfactual reports both guards rejecting, not a fabricated bad poster',()=>{
  const c=record.counterfactual;assert.equal(c.input.parameters.font_size,999);assert.equal(c.results.normal.error.type,'ActionValidationError');assert.equal(c.results.without_first_guard.error.type,'ValidationError');
  for(const r of Object.values(c.results) as any[]){assert.equal(r.accepted,false);assert.deepEqual(r.caller_layout_before,r.caller_layout_after);}
});
