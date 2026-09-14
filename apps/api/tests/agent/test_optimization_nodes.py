from pathlib import Path

from app.agent.nodes.apply_optimization import apply_optimization
from app.agent.nodes.evaluate import evaluate_draft, evaluate_optimized
from app.agent.nodes.generate_visual import generate_visual
from app.agent.nodes.plan_optimization import plan_optimization
from app.agent.nodes.render_draft import render_draft
from app.poster.renderer import PosterRenderer
from tests.agent.test_rendering_nodes import FakeImageProvider, _state


class FakeOptimizationProvider:
    async def complete_json(self, messages):
        assert "OptimizationPlan" in str(messages)
        return {
            "target_issues": ["标题层级不足"],
            "actions": [
                {
                    "action": "set_font_size",
                    "target_id": "title",
                    "parameters": {"font_size": 108},
                    "reason": "强化标题层级",
                    "source_rule_ids": ["title_hierarchy"],
                }
            ],
            "regenerate_visual": False,
        }


async def test_evaluate_plan_apply_and_reevaluate_layout_optimization(tmp_path: Path) -> None:
    state = _state()
    # Exercise an actual hierarchy defect, not absence of optional organizer text.
    next(element for element in state["design_spec"].layout.elements if element.role == "title").font_size = 32
    generated = await generate_visual(
        state,
        image_provider=FakeImageProvider(),
        run_directory=tmp_path,
    )
    rendered = render_draft(
        {**state, **generated},
        renderer=PosterRenderer(),
        run_directory=tmp_path,
    )
    initial_state = {**state, **generated, **rendered}

    evaluated = await evaluate_draft(initial_state)
    planned = await plan_optimization(
        {**initial_state, **evaluated},
        text_provider=FakeOptimizationProvider(),
    )
    optimized = apply_optimization(
        {**initial_state, **evaluated, **planned},
        renderer=PosterRenderer(),
        run_directory=tmp_path,
    )
    reevaluated = await evaluate_optimized({**initial_state, **evaluated, **planned, **optimized})

    assert evaluated["evaluation_initial"].scores.hard_rules < 40
    assert planned["optimization_plan"].actions[0].target_id == "title"
    title = next(element for element in optimized["layout"].elements if element.id == "title")
    assert title.font_size == 108
    assert Path(optimized["poster_optimized_path"]).is_file()
    assert reevaluated["evaluation_optimized"].evaluator_version == "evaluation-v2-aoi-paint-order"
    assert [event["node"] for event in reevaluated["events"]][-4:] == [
        "evaluate_draft",
        "plan_optimization",
        "apply_optimization",
        "evaluate_optimized",
    ]
