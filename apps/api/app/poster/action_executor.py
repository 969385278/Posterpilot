from collections.abc import Sequence

from app.poster.action_validator import validate_actions
from app.schemas.layout import NormalizedBox, PosterLayout
from app.schemas.optimization import OptimizationAction

_LAYOUT_ACTIONS = {
    "set_position",
    "set_size",
    "set_font_size",
    "set_color",
    "set_line_spacing",
    "set_alignment",
    "set_opacity",
}


def apply_optimization_actions(
    layout: PosterLayout,
    actions: Sequence[OptimizationAction],
) -> PosterLayout:
    """Apply only validated layout actions and revalidate all resulting bounds."""
    validate_actions(actions, layout)
    unsupported_actions = {
        action.action
        for action in actions
        if action.action not in _LAYOUT_ACTIONS
    }
    unsupported = sorted(unsupported_actions)
    if unsupported:
        raise ValueError(f"actions require a non-layout execution path: {', '.join(unsupported)}")
    updated = layout.model_copy(deep=True)
    elements = {element.id: element for element in updated.elements}
    for action in actions:
        element = elements[action.target_id]
        params = action.parameters
        if action.action == "set_position":
            element.box = NormalizedBox(
                x=float(params["x"]),
                y=float(params["y"]),
                width=element.box.width,
                height=element.box.height,
            )
        elif action.action == "set_size":
            element.box = NormalizedBox(
                x=element.box.x,
                y=element.box.y,
                width=float(params["width"]),
                height=float(params["height"]),
            )
        elif action.action == "set_font_size":
            element.font_size = int(params["font_size"])
        elif action.action == "set_color":
            element.color = str(params["color"])
        elif action.action == "set_line_spacing":
            element.line_spacing = float(params["line_spacing"])
        elif action.action == "set_alignment":
            element.alignment = str(params["alignment"])
        elif action.action == "set_opacity":
            element.opacity = float(params["opacity"])
    return PosterLayout.model_validate(updated.model_dump())
