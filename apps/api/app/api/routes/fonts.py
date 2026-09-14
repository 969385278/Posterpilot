import io
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont

from app.poster.font_catalog import FONTS, bundled_font_path
from app.poster.renderer import _font_path
from app.poster.typography import fit_text

router = APIRouter(tags=["title-fonts"])


@router.get("/title-fonts")
def list_title_fonts():
    return [{"id": key, "name": value[1], "description": value[2], "license": "OFL-1.1",
             "available": bundled_font_path(key).is_file(),
             "source": f"https://github.com/google/fonts/tree/main/ofl/{key}"}
            for key, value in FONTS.items()]


@lru_cache(maxsize=64)
def _preview(font_id: str, text: str) -> bytes:
    path = _font_path("reference-sans-bold" if font_id == "standard" else "open-" + font_id, text)
    layout = fit_text(text, font_path=path, requested_size=72, min_size=12, max_width=1056, max_height=144)
    font = ImageFont.truetype(str(path), layout.font_size)
    image = Image.new("RGB", (1100, 180), "#F4F7FB")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(layout.lines):
        left, top, right, bottom = font.getbbox(line)
        draw.text((22-left, 18+index*layout.line_height-top), line, font=font, fill="#183B66")
    result = io.BytesIO()
    image.save(result, format="PNG")
    return result.getvalue()


@router.get("/title-fonts/{font_id}/preview")
def preview_title_font(font_id: str, text: str = Query(default="摄影社招新", min_length=1, max_length=120)):
    if font_id not in FONTS and font_id != "standard":
        raise HTTPException(404, "字体不存在。")
    if font_id in FONTS and not bundled_font_path(font_id).is_file():
        raise HTTPException(404, "字体尚未安装。")
    return Response(_preview(font_id, text.strip() or "摄影社招新"), media_type="image/png",
                    headers={"Cache-Control": "private, max-age=300"})
