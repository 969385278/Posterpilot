import pytest
from pydantic import ValidationError

from app.schemas.react import (
    HumanCheckpoint,
    HumanDecision,
    ReactDecision,
    RoundSnapshot,
    ToolTrace,
)
from app.schemas.run import RunRecord
from tests.schemas.test_brief import valid_brief_data


def test_human_instruction_requires_non_empty_text() -> None:
    with pytest.raises(ValidationError):
        HumanDecision(action="instruct", instruction="   ")

    decision = HumanDecision(action="instruct", instruction="不要改变主视觉，只增强标题")

    assert decision.instruction == "不要改变主视觉，只增强标题"


def test_non_instruction_decision_rejects_instruction_payload() -> None:
    with pytest.raises(ValidationError):
        HumanDecision(action="approve", instruction="偷偷指定工具")


def test_react_tool_call_must_use_semantic_tool_whitelist() -> None:
    with pytest.raises(ValidationError):
        ReactDecision(
            decision="tool_call",
            summary="执行任意代码",
            tool_name="run_python",
            arguments={},
        )

    decision = ReactDecision(
        decision="tool_call",
        summary="先检索标题层级知识",
        tool_name="search_design_knowledge",
        arguments={"query": "标题不突出"},
    )

    assert decision.tool_name == "search_design_knowledge"


def test_finish_round_cannot_smuggle_tool_arguments() -> None:
    with pytest.raises(ValidationError):
        ReactDecision(
            decision="finish_round",
            summary="结束本轮",
            tool_name="modify_layout",
            arguments={"path": "../../secret"},
        )


def test_checkpoint_and_round_snapshot_are_serializable() -> None:
    trace = ToolTrace(
        round_number=1,
        step=1,
        decision_summary="放大标题",
        tool_name="modify_typography",
        tool_args={"actions": []},
        observation="标题字号已更新",
        success=True,
    )
    checkpoint = HumanCheckpoint(
        round_number=1,
        score=76.5,
        primary_issues=["标题层级不足"],
        suggestion="优先增强标题，再检查信息区密度。",
        citations=[],
        tool_traces=[trace],
    )
    snapshot = RoundSnapshot(
        round_number=1,
        poster_artifact="poster_round_1.png",
        attention_artifact="attention_round_1.png",
        score=82.0,
        score_delta=5.5,
        evaluation={"scores": {"total": 82.0}},
        tool_traces=[trace],
    )

    assert checkpoint.model_dump(mode="json")["round_number"] == 1
    assert snapshot.model_dump(mode="json")["tool_traces"][0]["step"] == 1


def test_run_record_accepts_waiting_for_human_status() -> None:
    record = RunRecord.model_validate(
        {"brief": valid_brief_data(), "status": "waiting_for_human"}
    )

    assert record.status == "waiting_for_human"

