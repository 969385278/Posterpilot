from pathlib import Path

from app.agent.nodes.common import with_event
from app.agent.state import PosterAgentState
from app.poster.renderer import PosterRenderer
from app.schemas.design_control import BackgroundTreatment


def render_draft(
    state: PosterAgentState,
    *,
    renderer: PosterRenderer,
    run_directory: Path | str,
) -> dict[str, object]:
    design_spec = state["design_spec"]
    main_visual_path = state["main_visual_path"]
    if design_spec is None or not main_visual_path:
        raise ValueError("design spec and main visual are required before rendering")
    result = renderer.render(
        design_spec.layout,
        main_visual_path=main_visual_path,
        output_path=Path(run_directory) / "poster_initial.png",
        background_color=design_spec.palette.background,
        treatment=state.get("background_treatment") or BackgroundTreatment(),
    )
    return {
        "poster_initial_path": str(result.path),
        "rendered_text_facts": result.text_facts,
        "events": with_event(
            state,
            node="render_draft",
            message="已完成初版海报程序化排版。",
            payload={"element_count": len(result.elements)},
        ),
    }
