from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.poster.typography import fit_text
from app.poster.font_catalog import FONT_ROOT, bundled_font_name, bundled_font_path, supports_text
from app.poster.color_treatment import treat_background
from app.schemas.design_control import BackgroundTreatment, RenderedTextFact
from app.schemas.layout import LayoutElement, PosterLayout


@dataclass(frozen=True, slots=True)
class PixelBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class RenderedElement:
    id: str
    actual_box: PixelBox


@dataclass(frozen=True, slots=True)
class RenderResult:
    path: Path
    elements: list[RenderedElement]
    text_facts: list[RenderedTextFact] = field(default_factory=list)


class PosterRenderer:
    def render(
        self,
        layout: PosterLayout,
        *,
        main_visual_path: Path | str,
        output_path: Path | str,
        background_color: str,
        treatment: BackgroundTreatment | None = None,
    ) -> RenderResult:
        visual_path = Path(main_visual_path)
        if not visual_path.is_file():
            raise FileNotFoundError(f"Main visual file does not exist: {visual_path}")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGB", (layout.canvas.width, layout.canvas.height), background_color)
        rendered: list[RenderedElement] = []
        text_facts: list[RenderedTextFact] = []

        main_visual = next(
            (element for element in layout.elements if element.role == "main_visual"),
            None,
        )
        full_canvas_box = PixelBox(
            x=0,
            y=0,
            width=layout.canvas.width,
            height=layout.canvas.height,
        )
        if main_visual is not None:
            _draw_main_visual(canvas, visual_path, full_canvas_box, treatment)

        if layout.readability_scrims:
            _draw_readability_scrims(canvas)
        draw = ImageDraw.Draw(canvas)

        for element in layout.elements:
            pixel_box = _to_pixel_box(element, layout)
            if element.role == "main_visual":
                rendered.append(RenderedElement(id=element.id, actual_box=full_canvas_box))
            elif element.content:
                if element.opacity < 1:
                    text_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                    actual_box, fact = _draw_text(ImageDraw.Draw(text_layer), element, pixel_box)
                    alpha = text_layer.getchannel("A").point(
                        [round(value * element.opacity) for value in range(256)]
                    )
                    canvas.paste(text_layer, (0, 0), alpha)
                else:
                    actual_box, fact = _draw_text(draw, element, pixel_box)
                rendered.append(RenderedElement(id=element.id, actual_box=actual_box))
                text_facts.append(fact)

        canvas.save(output, format="PNG")
        return RenderResult(path=output, elements=rendered, text_facts=text_facts)


def _to_pixel_box(element: LayoutElement, layout: PosterLayout) -> PixelBox:
    box = element.box
    canvas = layout.canvas
    return PixelBox(
        x=round(box.x * canvas.width),
        y=round(box.y * canvas.height),
        width=round(box.width * canvas.width),
        height=round(box.height * canvas.height),
    )


def _draw_main_visual(
    canvas: Image.Image, path: Path, box: PixelBox,
    treatment: BackgroundTreatment | None = None,
) -> None:
    with Image.open(path) as source:
        fitted = ImageOps.fit(
            source.convert("RGB"),
            (box.width, box.height),
            method=Image.Resampling.LANCZOS,
        )
        canvas.paste(treat_background(fitted, treatment or BackgroundTreatment()), (box.x, box.y))


def _draw_readability_scrims(canvas: Image.Image) -> None:
    """Keep a full-bleed image visible while giving overlaid text stable contrast."""
    width, height = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    top_end = max(1, round(height * 0.32))
    bottom_start = round(height * 0.68)

    for y in range(top_end):
        progress = 1 - y / top_end
        alpha = round(158 * progress**1.6)
        overlay_draw.line((0, y, width, y), fill=(8, 13, 22, alpha))
    for y in range(bottom_start, height):
        progress = (y - bottom_start) / max(1, height - bottom_start)
        alpha = round(172 * progress**1.35)
        overlay_draw.line((0, y, width, y), fill=(8, 13, 22, alpha))

    composited = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    canvas.paste(composited)


def _draw_text(
    draw: ImageDraw.ImageDraw, element: LayoutElement, box: PixelBox,
) -> tuple[PixelBox, RenderedTextFact]:
    font_path = _font_path(element.font_family, element.content or "")
    requested_size = element.font_size or 32
    layout = fit_text(
        element.content or "",
        font_path=font_path,
        requested_size=requested_size,
        min_size=min(requested_size, 24),
        max_width=box.width,
        max_height=box.height,
        line_spacing=element.line_spacing,
    )
    font = ImageFont.truetype(str(font_path), layout.font_size)
    line_boxes: list[tuple[int, int, int, int]] = []
    for index, line in enumerate(layout.lines):
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
        line_width = right - left
        if element.alignment == "center":
            x = box.x + (box.width - line_width) // 2
        elif element.alignment == "right":
            x = box.x + box.width - line_width
        else:
            x = box.x
        y = box.y + index * layout.line_height
        draw.text(
            (x, y),
            line,
            font=font,
            fill=element.color or "#F8FAFC",
            stroke_width=max(1, round(layout.font_size / 42)),
            stroke_fill="#111827",
        )
        line_boxes.append((x + left, y + top, x + right, y + bottom))

    min_x = min((item[0] for item in line_boxes), default=box.x)
    min_y = min((item[1] for item in line_boxes), default=box.y)
    max_x = max((item[2] for item in line_boxes), default=box.x)
    max_y = max((item[3] for item in line_boxes), default=box.y)
    actual = PixelBox(min_x, min_y, max_x - min_x, max_y - min_y)
    fact = RenderedTextFact(
        element_id=element.id,
        content=element.content or "",
        requested_font_size=requested_size,
        actual_font_size=layout.font_size,
        font_name=bundled_font_name(font_path) if font_path.is_relative_to(FONT_ROOT) else " ".join(font.getname()),
        color=element.color or "#F8FAFC",
        opacity=element.opacity,
        line_count=len(layout.lines),
        fits_box=(
            layout.width <= box.width and layout.height <= box.height
            and min_x >= box.x and max_x <= box.x + box.width
            and min_y >= box.y and max_y <= box.y + box.height
        ),
        box=asdict(actual),
    )
    return actual, fact


def _font_path(font_family: str | None, text: str = "") -> Path:
    if font_family and font_family.startswith("open-"):
        try:
            path = bundled_font_path(font_family.removeprefix("open-"))
            if path.is_file() and supports_text(path, text):
                return path
        except ValueError:
            pass
        font_family = "reference-sans-bold"
    aliases = {
        "reference-serif": Path("C:/Windows/Fonts/simsun.ttc"),
        "reference-sans": Path("C:/Windows/Fonts/msyh.ttc"),
        "reference-sans-bold": Path("C:/Windows/Fonts/msyhbd.ttc"),
    }
    candidates = [
        aliases.get(font_family),
        Path(font_family) if font_family and Path(font_family).is_file() else None,
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError("No supported Chinese font file was found for poster rendering.")
