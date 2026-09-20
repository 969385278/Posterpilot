from pathlib import Path

from app.agent.nodes.common import with_event
from app.agent.state import PosterAgentState
from app.agent.tools.generation_tools import materialize_generated_image
from app.providers.image.base import ImageProvider


async def generate_visual(
    state: PosterAgentState,
    *,
    image_provider: ImageProvider,
    run_directory: Path | str,
) -> dict[str, object]:
    design_spec = state["design_spec"]
    if design_spec is None:
        raise ValueError("design spec is required before generating the main visual")
    generated = await image_provider.generate(design_spec.visual_prompt)
    output = await materialize_generated_image(
        generated,
        output_path=Path(run_directory) / "main_visual.png",
    )
    return {
        "main_visual_path": str(output),
        "events": with_event(
            state,
            node="generate_visual",
            message=("已载入审核过的公共领域原图作为展示背景，非模型生成。"
                     if generated.provider == "reviewed-public-domain-image" else "已生成无文字主视觉。"),
            payload={"provider": generated.provider, "model": generated.model},
        ),
    }
