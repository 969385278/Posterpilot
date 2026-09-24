from app.agent.tools.catalog import EXTENSION_SCHEMAS
from app.poster.design_guards import assert_design_constraints
from app.schemas.design_control import DesignControls
from app.schemas.layout import NormalizedBox, PosterLayout
from app.schemas.tool_release import AlignTextGroupArguments, TextOpacityArguments


def execute_extension(
    name: str,
    arguments: dict,
    layout: PosterLayout,
    *,
    controls: DesignControls,
    baseline: PosterLayout,
) -> tuple[PosterLayout, str]:
    schema = EXTENSION_SCHEMAS.get(name)
    if schema is None:
        raise ValueError("Unknown registered extension")
    parsed = schema.model_validate(arguments)
    updated = layout.model_copy(deep=True)
    elements = {item.id: item for item in updated.elements}
    ids = parsed.target_ids + (
        [parsed.reference_id] if isinstance(parsed, AlignTextGroupArguments) else []
    )
    if any(key not in elements or not elements[key].content for key in ids):
        raise ValueError("Extension tools require existing text elements")
    if any(elements[key].role == "main_visual" for key in ids):
        raise ValueError("Main visual cannot be edited by text tools")
    if isinstance(parsed, TextOpacityArguments):
        for key in parsed.target_ids:
            elements[key].opacity = parsed.opacity
        observation = f"已设置文字透明度为 {parsed.opacity:g}，待轮末检查实际可读性。"
    else:
        reference = elements[parsed.reference_id].box
        for key in parsed.target_ids:
            old = elements[key].box
            x = reference.x
            if parsed.edge == "center":
                x += (reference.width - old.width) / 2
            elif parsed.edge == "right":
                x += reference.width - old.width
            elements[key].box = NormalizedBox(
                x=x,
                y=old.y,
                width=old.width,
                height=old.height,
            )
        observation = f"已按参考文字框 {parsed.reference_id} 的 {parsed.edge} 边对齐，待轮末检查。"
    updated = PosterLayout.model_validate(updated.model_dump())
    assert_design_constraints(baseline, updated, controls)
    return updated, observation
