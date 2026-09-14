"""Project selected case dimensions onto a small, trusted set of render choices."""
from app.poster.layout_candidates import propose_layouts
from app.schemas.design_control import DesignControls
from app.schemas.layout import PosterLayout


def apply_case_references(layout: PosterLayout, cases: list[dict]) -> tuple[PosterLayout, list[str]]:
    result = layout.model_copy(deep=True)
    notes = []
    for case in cases:
        features = case.get("selected_features", {})
        hints = case.get("render_hints", {})
        if "typography" in features:
            style = hints.get("title_font_style", "sans")
            family = {"serif": "reference-serif", "sans": "reference-sans", "sans_bold": "reference-sans-bold"}.get(style)
            if family:
                for element in result.elements:
                    if element.role == "title":
                        element.font_family = family
                notes.append(f"{case['case_id']}：字体气质映射为可用中文字体预设 {style}，不是原作字体复刻；实际字体见渲染分析。")
        if "composition" in features:
            preset = hints.get("composition_preset", "top_title")
            label = {"top_title": "上方标题 · 下方信息", "bottom_title": "上方信息 · 下方标题", "center_title": "中段标题 · 下方信息"}.get(preset)
            selected = next((candidate for name, candidate in propose_layouts(result, DesignControls()) if name == label), None)
            if selected is not None:
                result = selected
                notes.append(f"{case['case_id']}：采用受限构图预设「{label}」，主视觉保持全幅；不是原作坐标复制。")
            else:
                notes.append(f"{case['case_id']}：构图预设不可用或与当前相同，保留当前文字布局；主视觉提示仍参考所选构图。")
    return result, notes
