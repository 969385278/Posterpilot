from pathlib import Path

from PIL import ImageFont

from app.poster.typography import fit_text, wrap_text

FONT_PATH = Path("C:/Windows/Fonts/msyh.ttc")


def test_wrap_text_keeps_chinese_punctuation_off_line_start() -> None:
    font = ImageFont.truetype(FONT_PATH, 36)

    lines = wrap_text("红楼梦研讨分享会，从人物关系看古典文学", font, max_width=180)

    assert len(lines) >= 2
    assert all(not line.startswith(("，", "。", "！", "？", "、", "：", "；")) for line in lines)


def test_fit_text_reduces_long_title_to_box_height() -> None:
    layout = fit_text(
        "红楼梦研讨分享会：从人物关系看古典文学的叙事魅力",
        font_path=FONT_PATH,
        requested_size=72,
        min_size=28,
        max_width=430,
        max_height=150,
        line_spacing=1.2,
    )

    assert layout.font_size < 72
    assert layout.height <= 150
    assert layout.lines


def test_narrow_columns_do_not_split_times_or_latin_words():
    font = ImageFont.truetype(FONT_PATH, 32)
    lines = wrap_text("2026年9月20日 18:30\n学生活动中心一楼", font, max_width=300)
    assert any("18:30" in line for line in lines)
    assert "0" not in [line.strip() for line in lines]
    assert any("PosterPilot" in line for line in wrap_text("欢迎加入 PosterPilot 活动", font, max_width=180))


def test_fit_text_also_shrinks_to_fit_an_unbreakable_token_width():
    fitted = fit_text("18:30", font_path=FONT_PATH, requested_size=72, min_size=16, max_width=100, max_height=150)
    assert fitted.width <= 100
    assert fitted.font_size < 72
    assert fitted.lines == ["18:30"]
