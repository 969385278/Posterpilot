import pytest

from app.poster.fact_edits import edited_layout, field_value, parse_fact_edits
from app.poster.design_guards import assert_design_constraints
from app.schemas.design_control import DesignControls
from tests.poster.test_action_validator import make_layout


def layout():
    value = make_layout()
    next(e for e in value.elements if e.id == "event_info").content = "11月8日 18:00\n东区礼堂"
    return value


def test_location_edit_preserves_time_and_rejects_unapproved_content():
    old = layout()
    edits = parse_fact_edits("请把地点改为西区展厅，其他活动信息不变。", old)
    controls = DesignControls(fact_edits=edits)
    new = edited_layout(old, edits)
    assert field_value(new, "location") == "西区展厅"
    assert field_value(new, "event_time") == "11月8日 18:00"
    assert_design_constraints(old, new, controls)
    next(e for e in new.elements if e.id == "event_info").content = "明天\n西区展厅"
    with pytest.raises(ValueError):
        assert_design_constraints(old, new, controls)


def test_stale_fact_edits_and_conflicting_preservation_are_rejected():
    old = layout()
    edits = parse_fact_edits("地点改为南区展厅", old)
    with pytest.raises(ValueError):
        edited_layout(edited_layout(old, edits), edits)
    with pytest.raises(ValueError):
        parse_fact_edits("请把地点改为南区展厅，同时地点保持不变。", old)
    with pytest.raises(ValueError):
        assert_design_constraints(old, edited_layout(old, edits), DesignControls(
            fact_edits=edits, locks=[{"element_id":"event_info","properties":["content"]}]))


def test_full_field_edit_does_not_touch_other_elements():
    old = layout()
    edits = parse_fact_edits("把标题改为秋日读书会", old)
    new = edited_layout(old, edits)
    assert field_value(new, "title") == "秋日读书会"
    assert [e for e in new.elements if e.id != "title"] == [e for e in old.elements if e.id != "title"]
