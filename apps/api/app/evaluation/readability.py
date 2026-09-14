"""Conservative sampled text/background contrast, not a WCAG certification.

Measurements use the actual fitted background and renderer scrims, before text.
The dark text stroke is intentionally not counted as a full stable backing field.
"""

from pathlib import Path

from PIL import Image, ImageColor, ImageOps

from app.poster.color_treatment import treat_background
from app.poster.renderer import _draw_readability_scrims
from app.schemas.design_control import BackgroundTreatment, RenderedTextFact, VerificationCheck
from app.schemas.layout import PosterLayout


def _luminance(rgb) -> float:
    channels = [value / 255 for value in rgb[:3]]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear, strict=True))


def text_readability_checks(
    layout: PosterLayout, *, main_visual_path: Path | str,
    treatment: BackgroundTreatment, text_facts: list[RenderedTextFact],
) -> list[VerificationCheck]:
    with Image.open(main_visual_path) as source:
        background = treat_background(ImageOps.fit(source.convert("RGB"), (layout.canvas.width, layout.canvas.height)), treatment)
    _draw_readability_scrims(background)
    checks = []
    for fact in text_facts:
        box = fact.box
        left, top = max(0, box["x"]), max(0, box["y"])
        right, bottom = min(background.width, box["x"] + box["width"]), min(background.height, box["y"] + box["height"])
        if right <= left or bottom <= top:
            checks.append(VerificationCheck(key=f"readability:{fact.element_id}", label=f"{fact.element_id} 文字可读性", status="unavailable", detail="没有有效文字区域用于对比度采样。"))
            continue
        sample = background.crop((left, top, right, bottom)).resize((12, 12))
        foreground = _luminance(ImageColor.getrgb(fact.color))
        luminances = (_luminance(sample.getpixel((x, y))) for y in range(12) for x in range(12))
        ratios = sorted((max(foreground, lum) + 0.05) / (min(foreground, lum) + 0.05) for lum in luminances)
        measured = ratios[int((len(ratios) - 1) * 0.1)]
        threshold = 3.0 if fact.actual_font_size >= 24 else 4.5
        checks.append(VerificationCheck(
            key=f"readability:{fact.element_id}", label=f"{fact.element_id} 文字可读性",
            status="passed" if measured >= threshold else "failed", after=round(measured, 3),
            detail=f"包围框背景采样对比度第 10 百分位 {measured:.2f}:1，参考门槛 {threshold:g}:1；不计描边，不证明实际阅读效果。",
        ))
    return checks
