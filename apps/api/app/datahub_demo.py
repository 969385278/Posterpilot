"""Isolated, clearly labelled offline factory for the two-project walkthrough."""

import json
from pathlib import Path

from app.core.paths import PROJECT_ROOT
from app.demo import DemoTextProvider, create_demo_app


class DataHubDemoTextProvider(DemoTextProvider):
    """Explicit deterministic fixture, also repairs contrast in the light test artwork."""

    async def complete_json(self, messages):
        decision = await super().complete_json(messages)
        if "ReAct Agent" in messages[0]["content"]:
            context = json.loads(messages[-1]["content"])
            if decision.get("tool_name") == "modify_typography":
                actions = decision["arguments"]["actions"]
                if any(action.get("target_id") == "title" for action in actions):
                    actions.append(
                        {
                            "action": "set_color",
                            "target_id": "title",
                            "parameters": {"color": "#182A40"},
                            "reason": "固定测试规则：浅背景配深色标题，不是模型自主学习。",
                        }
                    )
                elif not any(
                    element["id"] == "event_info"
                    for element in context["current_layout"]["elements"]
                ):
                    # This fixture can also run briefs without time/location.
                    decision = {
                        "decision": "finish_round",
                        "summary": "离线演示：没有活动信息元素，不执行不存在的目标。",
                    }
        return decision


def create_app(data_root: Path | None = None):
    return create_demo_app(
        data_root or PROJECT_ROOT / "data" / "datahub-demo", text_provider=DataHubDemoTextProvider()
    )
