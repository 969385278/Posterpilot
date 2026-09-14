"""Render the bundled font specimens locally, without model calls."""
import io
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.api.routes.fonts import _preview
from app.poster.font_catalog import FONTS

output = ROOT / "outputs/title-fonts"
output.mkdir(parents=True, exist_ok=True)
sheet = Image.new("RGB", (1100, len(FONTS) * 225), "#F4F7FB")
draw = ImageDraw.Draw(sheet)
label_font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
for index, (font_id, (_, label, _)) in enumerate(FONTS.items()):
    preview = _preview(font_id, "摄影社招新 春日音乐会")
    (output / f"{font_id}.png").write_bytes(preview)
    draw.text((22, index * 225 + 6), label, font=label_font, fill="#526274")
    sheet.paste(Image.open(io.BytesIO(preview)), (0, index * 225 + 40))
sheet.save(output / "字体预览总览.png")
print(output / "字体预览总览.png")
