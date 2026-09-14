from app.agent.nodes.evaluate import _annotate_fixation
from app.schemas.evaluation import Fixation
from app.schemas.layout import LayoutElement, NormalizedBox
from tests.agent.test_rendering_nodes import _state


def test_foreground_content_wins_over_full_bleed_visual() -> None:
    layout = _state()["design_spec"].layout
    for element in layout.elements:
        if element.role in {"title", "event_info", "organizer"}:
            point = Fixation(
                x=element.box.x + element.box.width / 2,
                y=element.box.y + element.box.height / 2,
                order=1,
            )
            assert _annotate_fixation(point, layout).aoi_role == element.role
            assert point.aoi_role is None


def test_last_painted_content_wins_and_unrendered_slot_is_ignored() -> None:
    layout = _state()["design_spec"].layout.model_copy(deep=True)
    box = NormalizedBox(x=0.4, y=0.4, width=0.2, height=0.2)
    layout.elements.extend([
        LayoutElement(id="overlay-first", role="decoration", box=box, content="first"),
        LayoutElement(id="overlay-last", role="logo", box=box, content="last"),
        LayoutElement(id="empty-slot", role="qr", box=box),
    ])
    assert _annotate_fixation(Fixation(x=0.5, y=0.5, order=1), layout).aoi_role == "logo"


def test_visual_covers_canvas_even_when_legacy_box_is_smaller() -> None:
    layout = _state()["design_spec"].layout.model_copy(deep=True)
    for element in layout.elements:
        if element.role == "main_visual":
            element.box = NormalizedBox(x=0.3, y=0.3, width=0.4, height=0.4)
    assert _annotate_fixation(Fixation(x=0, y=1, order=1), layout).aoi_role == "main_visual"
