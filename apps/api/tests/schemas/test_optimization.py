import pytest
from pydantic import ValidationError

from app.schemas.optimization import OptimizationPlan


def test_optimization_plan_accepts_whitelisted_actions() -> None:
    plan = OptimizationPlan.model_validate(
        {
            "target_issues": ["标题不是第一视觉焦点"],
            "actions": [
                {
                    "action": "set_font_size",
                    "target_id": "title",
                    "parameters": {"font_size": 92},
                    "reason": "提高标题层级",
                    "source_rule_ids": ["rule-layout-title-focus-001"],
                }
            ],
        }
    )

    assert plan.actions[0].action == "set_font_size"


def test_optimization_plan_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        OptimizationPlan.model_validate(
            {
                "target_issues": ["标题不醒目"],
                "actions": [
                    {
                        "action": "execute_python",
                        "target_id": "title",
                        "parameters": {"code": "print('unsafe')"},
                        "reason": "绕过动作校验",
                    }
                ],
            }
        )


def test_optimization_plan_rejects_empty_reason() -> None:
    with pytest.raises(ValidationError):
        OptimizationPlan.model_validate(
            {
                "target_issues": ["标题不醒目"],
                "actions": [
                    {
                        "action": "set_font_size",
                        "target_id": "title",
                        "parameters": {"font_size": 92},
                        "reason": "",
                    }
                ],
            }
        )
