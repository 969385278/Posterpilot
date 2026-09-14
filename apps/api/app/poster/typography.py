from dataclasses import dataclass
from pathlib import Path
import re

from PIL import ImageFont

FORBIDDEN_LINE_START = frozenset("，。！？、：；）】》」』")


@dataclass(frozen=True, slots=True)
class TextLayout:
    lines: list[str]
    font_size: int
    width: int
    height: int
    line_height: int


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    if max_width <= 0:
        raise ValueError("max_width must be positive")
    lines: list[str] = []
    current = ""
    # Keep times, numeric groups and Latin words intact. Character-by-character
    # wrapping used to turn 18:30 into 18:3 / 0 in narrow side-band candidates.
    tokens = re.findall(r"\n|[A-Za-z0-9]+(?:[.:/_-][A-Za-z0-9]+)*|.", text.strip())
    for token in tokens:
        if token == "\n":
            if current:
                lines.append(current)
                current = ""
            continue
        candidate = f"{current}{token}"
        if current and _text_width(font, candidate) > max_width:
            if token in FORBIDDEN_LINE_START:
                current = candidate
            else:
                lines.append(current)
                current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def fit_text(
    text: str,
    *,
    font_path: Path | str,
    requested_size: int,
    min_size: int,
    max_width: int,
    max_height: int,
    line_spacing: float = 1.2,
) -> TextLayout:
    if min_size > requested_size:
        raise ValueError("min_size must not exceed requested_size")
    if max_height <= 0:
        raise ValueError("max_height must be positive")
    for font_size in range(requested_size, min_size - 1, -1):
        font = ImageFont.truetype(str(font_path), font_size)
        lines = wrap_text(text, font, max_width)
        line_height = max(1, round(font_size * line_spacing))
        height = len(lines) * line_height
        width = max((_text_width(font, line) for line in lines), default=0)
        if height <= max_height and width <= max_width:
            return TextLayout(
                lines=lines,
                font_size=font_size,
                width=width,
                height=height,
                line_height=line_height,
            )
    font = ImageFont.truetype(str(font_path), min_size)
    lines = wrap_text(text, font, max_width)
    line_height = max(1, round(min_size * line_spacing))
    return TextLayout(
        lines=lines,
        font_size=min_size,
        width=max((_text_width(font, line) for line in lines), default=0),
        height=len(lines) * line_height,
        line_height=line_height,
    )


def _text_width(font: ImageFont.FreeTypeFont, text: str) -> int:
    left, _top, right, _bottom = font.getbbox(text)
    return right - left
