"""Canonical selectable title fonts and unambiguous display-name aliases."""

from typing import Literal, get_args

TitleFont = Literal[
    "auto",
    "standard",
    "mashanzheng",
    "longcang",
    "zhimangxing",
    "zcoolkuaile",
    "zcoolqingkehuangyou",
    "zcoolxiaowei",
]
TITLE_FONT_ALIASES = {
    "自动": "auto",
    "常规粗体": "standard",
    "马善政楷体": "mashanzheng",
    "马善政毛笔楷书": "mashanzheng",
    "马善政": "mashanzheng",
    "龙藏体": "longcang",
    "龙藏": "longcang",
    "志莽行书": "zhimangxing",
    "站酷快乐体": "zcoolkuaile",
    "站酷庆科黄油体": "zcoolqingkehuangyou",
    "站酷小薇体": "zcoolxiaowei",
}


def normalize_title_font(value: str) -> str:
    normalized = TITLE_FONT_ALIASES.get(value, value)
    if normalized not in get_args(TitleFont):
        raise ValueError("未知的标题字体，请选择受支持的字体")
    return normalized
