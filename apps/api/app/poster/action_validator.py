import re
from collections.abc import Sequence
from numbers import Real

from app.schemas.layout import PosterLayout
from app.schemas.optimization import OptimizationAction

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ActionValidationError(ValueError):
    pass


def validate_actions(actions: Sequence[OptimizationAction], layout: PosterLayout) -> None:
    elements = {element.id: element for element in layout.elements}
    for action in actions:
        element = elements.get(action.target_id)
        if element is None:
            raise ActionValidationError(f"Unknown layout element: {action.target_id}")
        _validate_action(action, element.role)


def _validate_action(action: OptimizationAction, role: str) -> None:
    params = action.parameters
    if action.action == "set_font_size":
        _require_number(params, "font_size", minimum=10, maximum=240)
        if role == "main_visual":
            raise ActionValidationError("font_size cannot target main_visual")
    elif action.action == "set_brightness":
        _require_number(params, "brightness", minimum=0.5, maximum=1.5)
        if role != "main_visual":
            raise ActionValidationError("brightness changes must target main_visual")
    elif action.action == "set_opacity":
        _require_number(params, "opacity", minimum=0, maximum=1)
    elif action.action == "set_line_spacing":
        _require_number(params, "line_spacing", minimum=0.8, maximum=3)
    elif action.action == "set_color":
        color = params.get("color")
        if not isinstance(color, str) or not HEX_COLOR.fullmatch(color):
            raise ActionValidationError("color must be a #RRGGBB value")
    elif action.action == "set_alignment":
        if params.get("alignment") not in {"left", "center", "right"}:
            raise ActionValidationError("alignment must be left, center, or right")
    elif action.action == "set_position":
        _require_number(params, "x", minimum=0, maximum=1)
        _require_number(params, "y", minimum=0, maximum=1)
        if role == "main_visual":
            raise ActionValidationError("main_visual must remain full-bleed")
    elif action.action == "set_size":
        _require_number(params, "width", minimum=0.03, maximum=1)
        _require_number(params, "height", minimum=0.03, maximum=1)
        if role == "main_visual":
            raise ActionValidationError("main_visual must remain full-bleed")
    elif action.action == "regenerate_visual" and role != "main_visual":
        raise ActionValidationError("regenerate_visual must target main_visual")


def _require_number(
    parameters: dict[str, object],
    key: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    value = parameters.get(key)
    if not isinstance(value, Real) or isinstance(value, bool):
        raise ActionValidationError(f"{key} must be a number")
    number = float(value)
    if not minimum <= number <= maximum:
        raise ActionValidationError(f"{key} must be between {minimum} and {maximum}")
    return number
