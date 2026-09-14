from pathlib import Path

from app.agent.nodes.common import with_event
from app.agent.state import PosterAgentState
from app.poster.action_executor import apply_optimization_actions
from app.poster.renderer import PosterRenderer


def apply_optimization(
    state: PosterAgentState,
    *,
    renderer: PosterRenderer,
    run_directory: Path | str,
) -> dict[str, object]:
    design_spec = state["design_spec"]
    plan = state["optimization_plan"]
    main_visual_path = state["main_visual_path"]
    if design_spec is None or plan is None or not main_visual_path:
        raise ValueError("design spec, optimization plan, and main visual are required")
    needs_visual_regeneration = plan.regenerate_visual or any(
        action.action == "regenerate_visual" for action in plan.actions
    )
    if needs_visual_regeneration:
        raise ValueError("main visual regeneration is not available in the layout-only path")
    layout = state["layout"] or design_spec.layout
    optimized_layout = apply_optimization_actions(layout, plan.actions)
    result = renderer.render(
        optimized_layout,
        main_visual_path=main_visual_path,
        output_path=Path(run_directory) / "poster_optimized.png",
        background_color=design_spec.palette.background,
    )
    return {
        "layout": optimized_layout,
        "poster_optimized_path": str(result.path),
        "iteration": 1,
        "events": with_event(
            state,
            node="apply_optimization",
            message="已应用白名单布局动作并渲染优化版海报。",
            payload={"action_count": len(plan.actions)},
        ),
    }
