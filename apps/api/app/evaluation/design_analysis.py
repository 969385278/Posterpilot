"""Small explainable measurements; subjective VLM opinions remain separate."""

from pathlib import Path
from statistics import median

from PIL import Image, ImageOps, ImageStat

from app.poster.color_treatment import treat_background
from app.schemas.design_control import (
    BackgroundTreatment, FeatureObservation, PosterAnalysis, RenderedTextFact,
)
from app.schemas.layout import PosterLayout
from app.evaluation.readability import text_readability_checks


def analyze_design(
    layout: PosterLayout,
    *,
    main_visual_path: Path | str,
    treatment: BackgroundTreatment,
    text_facts: list[RenderedTextFact],
    visual_summary: str = "",
) -> PosterAnalysis:
    with Image.open(main_visual_path) as source:
        background = treat_background(
            ImageOps.fit(source.convert("RGB"), (layout.canvas.width, layout.canvas.height)),
            treatment,
        )
    sample = background.resize((160, 200), Image.Resampling.LANCZOS)
    contrast = ImageStat.Stat(sample.convert("L")).stddev[0] / 255
    saturation = ImageStat.Stat(sample.convert("HSV").getchannel("S")).mean[0] / 255
    indexed = sample.quantize(colors=5)
    rgb_palette = indexed.getpalette() or []
    colors = sorted(indexed.getcolors() or [], reverse=True)
    palette = [
        "#" + "".join(f"{value:02X}" for value in rgb_palette[index * 3:index * 3 + 3])
        for _, index in colors
    ]
    elements = {element.id: element for element in layout.elements}
    title_sizes = [fact.actual_font_size for fact in text_facts if elements[fact.element_id].role == "title"]
    other_sizes = [fact.actual_font_size for fact in text_facts if elements[fact.element_id].role != "title"]
    emphasis = max(title_sizes) / median(other_sizes) if title_sizes and other_sizes else None
    density = sum(fact.box["width"] * fact.box["height"] for fact in text_facts) / (layout.canvas.width * layout.canvas.height)
    return PosterAnalysis(
        palette=palette,
        text_facts=text_facts,
        visual_summary=visual_summary,
        readability_checks=text_readability_checks(layout, main_visual_path=main_visual_path, treatment=treatment, text_facts=text_facts),
        warnings=[
            "明暗反差和饱和度测量无字背景，不代表配色协调程度或审美优劣。",
            "标题强调仅以实际字号比例近似；注意力预测与视觉判断另行展示。",
            *(["存在文字超出分配区域，需要检查。"] if any(not fact.fits_box for fact in text_facts) else []),
        ],
        features=[
            FeatureObservation(key="background_contrast", label="背景明暗反差", value=round(contrast, 5), unit="归一化亮度标准差", basis="image_measurement", explanation="无字背景缩略图的亮度标准差；不是文字对比度，也不是色相撞色程度。", controllable=True),
            FeatureObservation(key="background_saturation", label="背景饱和度", value=round(saturation, 5), unit="平均 HSV 饱和度", basis="image_measurement", explanation="无字背景缩略图的平均色彩饱和度，与明暗反差分开计算。", controllable=True),
            FeatureObservation(key="title_emphasis", label="标题字号层级", value=round(emphasis, 4) if emphasis is not None else None, unit="标题/其他文字字号中位数", basis="render_metadata", explanation="读取实际绘制字号，包含自动缩字号结果，不让视觉模型猜测字体。", controllable=True),
            FeatureObservation(key="information_density", label="文字区域占比", value=round(density, 4), unit="文字包围框面积/画布面积", basis="render_metadata", explanation="文字包围框面积之和，不等于真实字形面积；重叠另由规则检测。"),
        ],
    )
