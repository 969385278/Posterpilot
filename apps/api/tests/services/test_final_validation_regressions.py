from types import SimpleNamespace

import pytest

from app.schemas.brief import PosterBrief
from app.schemas.intent import IntentRequest
from app.schemas.react import HumanCheckpoint, HumanDecision
from app.schemas.design_control import DesignControls
from app.poster.template_loader import TemplateLoader
from app.poster.fact_edits import parse_fact_edits
from app.services.intent_router import IntentRouter
from tests.services.test_user_memory import make_runs
from tests.services.test_design_assistant import setup, answer
from app.schemas.assistant import QuestionRequest


@pytest.mark.asyncio
async def test_new_fact_round_does_not_repeat_previous_relative_goal(tmp_path):
    runs=make_runs(tmp_path)
    runs.executor=SimpleNamespace()
    brief=PosterBrief(title="测试",event_time="周六 19:00",location="东区礼堂")
    record=runs.create(brief);runs.repository.update_status(record.id,"waiting_for_human")
    pending=HumanCheckpoint(round_number=1,score=60,suggestion="请检查",layout=TemplateLoader().instantiate(
        brief.poster_type,brief).model_dump(mode="json"),controls=DesignControls(
            adjustments=[{"trait":"background_saturation","direction":"weaken"}],
            locks=[{"element_id":"title","properties":["position","typography"]}]))
    runs.artifacts.write_json(record.id,"pending_human.json",pending.model_dump(mode="json"))
    result=await IntentRouter(runs).resolve(IntentRequest(text="请把地点改为西区展厅，其他活动信息不变。",run_id=record.id))
    assert result.can_apply
    assert result.controls.adjustments==[]
    assert result.controls.fact_edits[0].after=="西区展厅"
    assert all('content' not in l.properties for l in result.controls.locks if l.element_id=='event_info')


@pytest.mark.asyncio
async def test_live_graph_fact_edit_is_rendered_and_verified(tmp_path):
    from uuid import uuid4
    from app.schemas.layout import PosterLayout
    from tests.agent.test_controlled_design import executor
    from tests.agent.test_generation_nodes import _brief
    agent=executor(tmp_path/'checkpoint.sqlite3');run_id=uuid4()
    try:
        first=await agent.start(_brief(),run_id=run_id,run_directory=tmp_path)
        edits=parse_fact_edits("地点改为西区展厅",PosterLayout.model_validate(first.checkpoint.layout))
        last=await agent.resume(run_id,HumanDecision(action='instruct',instruction='地点改为西区展厅',
            controls=DesignControls(fact_edits=edits)),run_directory=tmp_path)
        fact=next(f for f in last.checkpoint.analysis.text_facts if f.element_id=='event_info')
        assert '西区展厅' in fact.content and '2026年7月20日 19:00' in fact.content
        check=next(c for c in last.checkpoint.goal_verification.checks if c.key=='fact:location')
        assert check.status=='passed'
    finally:await agent.aclose()


@pytest.mark.asyncio
async def test_assistant_repairs_schema_once_without_executing_invalid_tool(tmp_path):
    _,assistant,provider=setup(tmp_path,[{'action':'answer','answer':None},answer()])
    result=await assistant.ask(QuestionRequest(question='解释当前结果'))
    assert not result.degraded and result.answer
    assert len(provider.messages)==2 and not result.trace


@pytest.mark.asyncio
async def test_assistant_retries_invalid_json_transport_once(tmp_path):
    from app.providers.llm.deepseek import ProviderResponseError
    _,assistant,_=setup(tmp_path,[])
    class InvalidThenValid:
        calls=0
        async def complete_json(self,messages):
            self.calls+=1
            if self.calls==1:
                raise ProviderResponseError('Invalid JSON',kind='invalid_response')
            return answer()
    provider=InvalidThenValid();assistant.provider=provider
    result=await assistant.ask(QuestionRequest(question='说明当前状态'))
    assert not result.degraded and provider.calls==2
