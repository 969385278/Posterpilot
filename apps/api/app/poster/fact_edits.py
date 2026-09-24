"""Explicit, optimistic text-field edits; never allow unconstrained text replacement."""

import re

from app.schemas.design_control import TextFactEdit

FIELDS = {
    "标题": ("title", "title"), "副标题": ("subtitle", "subtitle"),
    "时间": ("event_time", "event_info"), "地点": ("location", "event_info"),
    "主办方": ("organizer", "organizer"),
}


def field_value(layout, field):
    target = next(target for name, target in FIELDS.values() if name == field)
    element = next((e for e in layout.elements if e.id == target), None)
    if element is None or not element.content:
        raise ValueError("待修改的文字字段不存在")
    value = element.content
    if field in {"event_time", "location"}:
        parts = value.splitlines()
        if len(parts) != 2:
            raise ValueError("时间地点没有明确的两行结构，请在新建需求中修改")
        value = parts[0 if field == "event_time" else 1]
    elif field == "organizer":
        value = re.sub(r"^主办[：:]\s*", "", value)
    return value


def parse_fact_edits(text, layout):
    edits = []
    for clause in re.split(r"[，,。；;\n]|同时|然后", text):
        match = re.fullmatch(
            r"\s*(?:请)?(?:帮我)?(?:把|将)?(?:活动)?(副标题|标题|时间|地点|主办方)"
            r"(?:的)?(?:文字|内容|文案)?(?:修改为|更改为|改成|改为|更换为)\s*[“\"]?(.+?)[”\"]?\s*", clause)
        if not match:
            continue
        label, value = match.groups()
        field, target = FIELDS[label]
        if re.search(rf"(?<!其他){label}(?:的)?(?:内容|文字|文案)?(?:保持)?不变", text):
            raise ValueError("同一字段既要求修改又要求保持不变，请明确选择")
        edits.append(TextFactEdit(field=field, element_id=target,
                                 before=field_value(layout, field), after=value))
    if len({e.field for e in edits}) != len(edits):
        raise ValueError("同一字段存在多次修改，请提供唯一的新值")
    return edits


def edited_layout(layout, edits, *, allow_applied=False):
    updated = layout.model_copy(deep=True)
    for edit in edits:
        target = next(target for field, target in FIELDS.values() if field == edit.field)
        current = field_value(updated, edit.field)
        if edit.element_id == target and allow_applied and current == edit.after:
            continue
        if edit.element_id != target or current != edit.before:
            raise ValueError("文字事实已变化或字段不匹配，请刷新后重新确认")
        element = next(e for e in updated.elements if e.id == target)
        if edit.field in {"location", "event_time"}:
            lines = element.content.splitlines()
            lines[0 if edit.field == "event_time" else 1] = edit.after
            element.content = "\n".join(lines)
        elif edit.field == "organizer":
            prefix = re.match(r"^主办[：:]\s*", element.content)
            element.content = (prefix.group() if prefix else "") + edit.after
        else:
            element.content = edit.after
    return updated


def bind_instruction_edits(controls, text, layout):
    """Support the direct feedback form as well as the intent-preview entry point."""
    edits = parse_fact_edits(text or "", layout)
    if controls.fact_edits:
        # Structured confirmation may omit natural language, but may not
        # contradict a parseable explicit instruction.
        if edits and edits != controls.fact_edits:
            raise ValueError("文字替换预览与当前指令不一致，请重新解析")
        return controls
    return controls.model_copy(update={"fact_edits": edits}) if edits else controls
