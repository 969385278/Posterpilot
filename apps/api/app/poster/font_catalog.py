"""Curated, locally bundled OFL title fonts. IDs never become arbitrary paths."""
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

from app.core.paths import PROJECT_ROOT

FONT_ROOT = PROJECT_ROOT / "data/fonts/open-source"
FONTS = {
    "mashanzheng": ("MaShanZheng-Regular.ttf", "马善政毛笔体", "厚实毛笔，适合国风、传统文化标题"),
    "longcang": ("LongCang-Regular.ttf", "龙藏体", "疏朗手写，适合文艺、书信感标题"),
    "zhimangxing": ("ZhiMangXing-Regular.ttf", "志莽行书", "连笔行草，适合短标题；长文字慎用"),
    "zcoolkuaile": ("ZCOOLKuaiLe-Regular.ttf", "站酷快乐体", "活泼不规则笔画，适合社团招新、趣味活动"),
    "zcoolqingkehuangyou": ("ZCOOLQingKeHuangYou-Regular.ttf", "站酷庆科黄油体", "窄长圆角字形，适合现代醒目标题"),
    "zcoolxiaowei": ("ZCOOLXiaoWei-Regular.ttf", "站酷小薇体", "装饰宋体气质，适合文化、展览标题"),
}


def bundled_font_path(font_id: str) -> Path:
    if font_id not in FONTS:
        raise ValueError("Unknown title font")
    return FONT_ROOT / font_id / FONTS[font_id][0]


@lru_cache(maxsize=32)
def _codepoints(path: str, modified_ns: int) -> frozenset[int]:
    with TTFont(path, fontNumber=0, lazy=True) as font:
        return frozenset((font.getBestCmap() or {}).keys())


def supports_text(path: Path, text: str) -> bool:
    return all(ord(char) in _codepoints(str(path), path.stat().st_mtime_ns)
               for char in text if not char.isspace())


@lru_cache(maxsize=16)
def bundled_font_name(path: Path) -> str:
    # FreeType can expose Chinese name records as literal question marks on
    # Windows. Read the font's English Unicode name table, not a guessed label.
    with TTFont(str(path), lazy=True) as font:
        table = font["name"]
        parts = []
        for name_id in (1, 2):
            record = table.getName(name_id, 3, 1, 0x409) or table.getName(name_id, 1, 0, 0)
            if record:
                parts.append(record.toUnicode())
        return " ".join(parts) or path.stem


def select_title_font(layout, brief, cases):
    """Explicit user choice wins; auto respects selected case typography first."""
    result = layout.model_copy(deep=True)
    if brief.title_font == "auto" and any("typography" in case.get("selected_features", {}) for case in cases):
        return result, "标题字体沿用所选案例的相似风格预设。"
    selected = brief.title_font
    if selected == "auto":
        selected = {"cultural_event": "zcoolxiaowei", "club_recruitment": "zcoolkuaile",
                    "campus_lecture": "zcoolqingkehuangyou"}[brief.poster_type]
    if selected == "standard":
        family, explanation = "reference-sans-bold", "标题使用常规粗体，正文不变。"
    else:
        path = bundled_font_path(selected)
        if not path.is_file() or not supports_text(path, brief.title):
            family = "reference-sans-bold"
            explanation = f"{FONTS[selected][1]}未安装或不支持标题中的部分字符，整个标题回退为常规粗体；实际字体见渲染分析。"
        else:
            family = "open-" + selected
            explanation = f"标题使用开源字体「{FONTS[selected][1]}」（OFL-1.1），正文不变。"
    for element in result.elements:
        if element.role == "title":
            element.font_family = family
    return result, explanation
