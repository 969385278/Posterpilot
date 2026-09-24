"""Offline capture. Uses unchanged production code + existing test providers.

Explicit CLI command only: the website has no link to this script or Python.
Writes solely inside this tool's .runtime and public/case folders.
"""
import ast
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from uuid import uuid4

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))

from app.agent.executor import LangGraphAgentExecutor
from app.poster.renderer import PosterRenderer
from app.schemas.react import HumanDecision
from app.schemas.optimization import OptimizationAction
from app.poster.action_executor import apply_optimization_actions
from tests.agent.test_hitl_executor import BothStageRetriever, DesignAndReactProvider
from tests.agent.test_generation_nodes import _brief
from tests.agent.test_rendering_nodes import FakeImageProvider

OUT = HERE / 'public/case'
RAW = HERE / '.runtime' / ('capture-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
RUN_ID = uuid4()
provider_calls = []
image_calls = []
render_calls = []


def safe(value):
    if hasattr(value, 'model_dump'):
        return safe(value.model_dump(mode='json'))
    if isinstance(value, dict):
        return {str(k): safe(v) for k,v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(v) for v in value]
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        return value.replace(str(RAW), '{CAPTURE_DIR}').replace(str(ROOT), '{REPOSITORY}').replace(str(RUN_ID), 'chapter-task-001')
    if value is None or isinstance(value, (float, int, bool)):
        return value
    return str(type(value).__name__)


def save(name, value):
    (OUT/name).write_text(json.dumps(safe(value), ensure_ascii=False, indent=2), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecordedProvider(DesignAndReactProvider):
    async def complete_json(self, messages):
        result = await super().complete_json(messages)
        provider_calls.append({'input':safe(messages),'output':safe(result),'kind':'test-double'})
        return result


class RecordedImage(FakeImageProvider):
    async def generate(self, prompt, **kwargs):
        result = await super().generate(prompt, **kwargs)
        image_calls.append({'prompt':prompt,'provider':result.provider,'model':result.model,'kind':'test-double'})
        return result


class RecordedRenderer(PosterRenderer):
    def render(self, layout, **kwargs):
        result = super().render(layout, **kwargs)
        render_calls.append({'input':safe({'layout':layout,**kwargs}), 'output':safe({'path':result.path,'text_facts':result.text_facts}), 'sha256':sha(result.path)})
        return result


def source_ref(relative, symbol, highlights=None):
    path = ROOT/relative
    contents = path.read_text(encoding='utf-8-sig')
    body = ast.parse(contents).body
    for part in symbol.split('.'):
        found = next(n for n in body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==part)
        body = found.body
    return {'id':relative+'#'+symbol,'path':relative,'symbol':symbol,'start':found.lineno,'end':found.end_lineno,
            'code':'\n'.join(contents.splitlines()[found.lineno-1:found.end_lineno]),'sha256':sha(path),
            'highlights':highlights or [found.lineno,found.end_lineno]}


def snapshot(s):
    return {'values':safe(s.values),'next':list(s.next),'step':s.metadata.get('step'),
            'checkpoint_id':s.config.get('configurable',{}).get('checkpoint_id'),
            'interrupts':[safe(i.value) for task in s.tasks for i in task.interrupts]}


async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    RAW.mkdir(parents=True,exist_ok=False)
    # Reject outbound network at its actual socket boundary. Async loop's local
    # socketpair remains usable; no service/provider is allowed to connect.
    original_connect = socket.socket.connect
    def no_network(*args, **kwargs):
        raise AssertionError('Network is disabled during this offline capture')
    socket.socket.connect = no_network
    common = dict(retriever=BothStageRetriever(),image_provider=RecordedImage(),renderer=RecordedRenderer(),checkpoint_path=RAW/'checkpoint.sqlite3')
    first = LangGraphAgentExecutor(text_provider=RecordedProvider(), **common)
    started = await first.start(_brief(),run_id=RUN_ID,run_directory=RAW)
    graph = await first._ensure_graph()
    config = first._config(RUN_ID)
    initial = snapshot(await graph.aget_state(config))
    before_hash = sha(RAW/'main_visual.png')
    await first.aclose()
    counts_before = {'image_calls':len(image_calls),'text_calls':len(provider_calls),'renders':len(render_calls)}
    second = LangGraphAgentExecutor(text_provider=RecordedProvider(expected_instruction='不要改变主视觉'), **common)
    decision = HumanDecision(action='instruct',instruction='不要改变主视觉，只增强标题')
    restored = snapshot(await (await second._ensure_graph()).aget_state(second._config(RUN_ID)))
    outcome = await second.resume(RUN_ID,decision,run_directory=RAW)
    graph = await second._ensure_graph()
    history = [snapshot(s) async for s in graph.aget_state_history(config)]
    history.sort(key=lambda s:s['step'])
    resumed_history = [s for s in history if s['step'] > initial['step']]
    final = snapshot(await graph.aget_state(config))
    await second.aclose()
    after_hash = sha(RAW/'main_visual.png')
    assert initial['values'] == restored['values']
    assert started.status == outcome.status == 'waiting_for_human'
    assert len(image_calls) == counts_before['image_calls'] == 1
    assert before_hash == after_hash
    assert outcome.checkpoint.tool_traces[0].success
    assert len(outcome.checkpoint.rounds) == 1

    # Counterfactual changes only one guard in an isolated copied AST. The actual
    # production function/module is never patched, and no production file changes.
    import app.poster.action_executor as actions_module
    raw_text=(ROOT/'apps/api/app/poster/action_executor.py').read_text(encoding='utf-8')
    tree=ast.parse(raw_text)
    fn=copy.deepcopy(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='apply_optimization_actions'))
    removed=[n.lineno for n in fn.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='validate_actions']
    fn.body=[n for n in fn.body if n.lineno not in removed]
    isolated=dict(vars(actions_module))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<isolated-counterfactual>','exec'),isolated)
    from app.schemas.layout import PosterLayout
    base_layout=PosterLayout.model_validate(initial['values']['layout'])
    invalid=OptimizationAction(action='set_font_size',target_id='title',parameters={'font_size':999},reason='隔离测试：超出字号范围')
    results={}
    for name,call in [('normal',apply_optimization_actions),('without_first_guard',isolated['apply_optimization_actions'])]:
        before=base_layout.model_dump(mode='json')
        try:
            result=call(base_layout,[invalid])
            results[name]={'accepted':True,'output':safe(result),'error':None}
        except Exception as error:
            results[name]={'accepted':False,'output':{'collected':False,'reason':'函数抛出异常，没有返回布局'},'error':{'type':type(error).__name__,'message':str(error)}}
        results[name]['caller_layout_before']=before
        results[name]['caller_layout_after']=base_layout.model_dump(mode='json')
    assert results['normal']['error']['type']=='ActionValidationError'
    assert results['without_first_guard']['error']['type']=='ValidationError'
    assert all(r['caller_layout_before']==r['caller_layout_after'] for r in results.values())
    socket.socket.connect=original_connect

    refs=[('apps/api/app/agent/executor.py','LangGraphAgentExecutor.resume'),
          ('apps/api/app/agent/executor.py','LangGraphAgentExecutor._config'),
          ('apps/api/app/agent/nodes/human_review.py','human_review'),
          ('apps/api/app/agent/nodes/react_decide.py','react_decide'),
          ('apps/api/app/agent/nodes/execute_react_tool.py','execute_react_tool'),
          ('apps/api/app/agent/tools/react_tools.py','ReactToolRegistry.execute'),
          ('apps/api/app/poster/action_executor.py','apply_optimization_actions'),
          ('apps/api/app/poster/action_validator.py','_validate_action'),
          ('apps/api/app/poster/action_validator.py','_require_number'),
          ('apps/api/app/schemas/layout.py','LayoutElement'),
          ('apps/api/app/agent/nodes/complete_round.py','render_round'),
          ('apps/api/app/agent/nodes/evaluate.py','evaluate_optimized'),
          ('apps/api/app/agent/nodes/complete_round.py','complete_round'),
          ('apps/api/app/agent/nodes/propose_layouts.py','propose_layout_candidates'),
          ('apps/api/app/agent/nodes/human_review.py','build_human_checkpoint'),
          ('apps/api/tests/agent/test_hitl_executor.py','test_executor_pauses_resumes_one_round_and_finishes'),
          ('apps/api/tests/agent/test_hitl_executor.py','DesignAndReactProvider'),
          ('apps/api/tests/agent/test_rendering_nodes.py','FakeImageProvider')]
    sources=[source_ref(*ref) for ref in refs]
    assets=[]
    for name in ['poster_initial.png','poster_round_1.png','main_visual.png']:
        shutil.copy2(RAW/name,OUT/name)
        assets.append({'file':name,'sha256':sha(RAW/name),'kind':'test-double','description':'由当前业务渲染器实际写出的测试产物；背景来自 FakeImageProvider' if name!='main_visual.png' else '测试图片提供者产生的单色背景，不是真实生图模型输出'})
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tracked_diff=subprocess.check_output(['git','diff','--','apps/api'],cwd=ROOT,text=True)
    assert not tracked_diff, 'Business code must remain unchanged'
    record={
        'schemaVersion':1,'id':'preserve-background-enlarge-title','evidenceKind':'test-double',
        'capturedAt':datetime.now(timezone.utc).isoformat(),'commit':commit,
        'businessSourceModified':False,'collector':{'path':'apps/execution-learner/scripts/capture_case.py','sha256':sha(Path(__file__))},
        'provenance':'当前仓库已有集成测试的场景，执行真实 LangGraph/SQLite/工具/Pillow；模型、图片和检索使用现有测试替身。',
        'limitations':['没有运行网页/API/SSE，前端事件通知未采集。','没有真实模型响应或真实用户审美结论。','关键节点边界来自持久化检查点，不是逐行 Python 调试记录。','真实业务耗时未采集；播放器时间仅是教学节奏。'],
        'missing':{'real_model_output':'未采集（使用测试替身）','frontend_sse':'未采集（直接执行 Executor）','wall_clock_duration':'未采集'},
        'versions':{p:importlib.metadata.version(p) for p in ['langgraph','langgraph-checkpoint-sqlite','pydantic','pillow']},
        'decision':safe(decision),'initial':initial,'restored':restored,'history':resumed_history,'final':final,
        'initialOutcome':safe(started),'outcome':safe(outcome),'providerCalls':provider_calls,
        'imageCalls':image_calls,'renderCalls':render_calls,'countsBeforeResume':counts_before,
        'backgroundEvidence':{'beforeSha256':before_hash,'afterSha256':after_hash,'imageCallsBefore':counts_before['image_calls'],'imageCallsAfter':len(image_calls),'sameFileBytes':before_hash==after_hash},
        'assets':assets,'sources':sources,
        'counterfactual':{'id':'font-size-validation','evidenceKind':'test-double','correspondingStep':'execute-tool',
            'input':safe(invalid),'changedCondition':'仅在隔离函数副本中删除 validate_actions(actions, layout) 这一行',
            'removedLines':removed,'sourceSha256':sha(ROOT/'apps/api/app/poster/action_executor.py'),
            'results':results,'conclusion':'去掉第一层校验后，最终 PosterLayout 的 Pydantic 校验仍拒绝 999；不能声称只去掉这一层就会产生坏海报。两次调用均未修改调用方传入的布局。'}
    }
    save('record.json',record)
    print(json.dumps({'status':'captured','history':[(s['step'],s['next']) for s in resumed_history], 'assets':assets,'before_title':next(x['font_size'] for x in initial['values']['layout']['elements'] if x['id']=='title'),'after_title':next(x['font_size'] for x in final['values']['layout']['elements'] if x['id']=='title')},ensure_ascii=True))


if __name__=='__main__':
    asyncio.run(main())
