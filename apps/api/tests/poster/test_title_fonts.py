import hashlib
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.api.routes.fonts import router, _preview
from app.poster.font_catalog import FONT_ROOT, FONTS, bundled_font_path, select_title_font, supports_text
from app.poster.renderer import PosterRenderer, _font_path
from app.poster.template_loader import TemplateLoader
from app.schemas.brief import PosterBrief


@pytest.mark.parametrize("font_id", list(FONTS))
def test_bundled_font_license_hash_and_real_render(font_id, tmp_path):
    manifest = json.loads((FONT_ROOT / "manifest.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["fonts"] if item["id"] == font_id)
    for record in entry["files"]:
        data = (FONT_ROOT / font_id / record["name"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record["sha256"]
    assert "SIL OPEN FONT LICENSE Version 1.1" in (FONT_ROOT / font_id / "OFL.txt").read_text()
    brief = PosterBrief(title="摄影社招新", title_font=font_id)
    layout, note = select_title_font(TemplateLoader().instantiate(brief.poster_type, brief), brief, [])
    assert layout.elements[0].font_family == "open-" + font_id
    assert supports_text(bundled_font_path(font_id), brief.title)
    image = tmp_path / "background.png"
    Image.new("RGB", (1080, 1440), "#304560").save(image)
    result = PosterRenderer().render(layout, main_visual_path=image, output_path=tmp_path / "poster.png", background_color="#304560")
    assert result.path.exists()
    assert result.text_facts[0].content == brief.title
    assert result.text_facts[0].fits_box
    assert "?" not in result.text_facts[0].font_name
    assert _font_path(layout.elements[0].font_family, brief.title) == bundled_font_path(font_id)
    assert Image.open(io.BytesIO(_preview(font_id, brief.title))).size == (1100, 180)


def test_explicit_font_wins_case_reference_and_auto_respects_case():
    brief = PosterBrief(title="招新", title_font="mashanzheng")
    layout = TemplateLoader().instantiate(brief.poster_type, brief)
    layout.elements[0].font_family = "reference-serif"
    cases = [{"selected_features": {"typography": "宋体"}}]
    selected, _ = select_title_font(layout, brief, cases)
    assert selected.elements[0].font_family == "open-mashanzheng"
    brief.title_font = "auto"
    selected, _ = select_title_font(layout, brief, cases)
    assert selected.elements[0].font_family == "reference-serif"


def test_missing_glyphs_fall_back_as_whole_title():
    brief = PosterBrief(title="招新\U00020000", title_font="zcoolkuaile")
    selected, note = select_title_font(TemplateLoader().instantiate(brief.poster_type, brief), brief, [])
    assert selected.elements[0].font_family == "reference-sans-bold"
    assert "回退" in note


def test_font_api_and_unknown_font_rejection():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert len(client.get("/title-fonts").json()) == 6
    assert client.get("/title-fonts/mashanzheng/preview?text=招新").headers["content-type"] == "image/png"
    assert client.get("/title-fonts/unknown/preview").status_code == 404
    assert client.get("/title-fonts/mashanzheng/preview", params={"text": "a" * 121}).status_code == 422
    with pytest.raises(ValidationError):
        PosterBrief(title="招新", title_font="C:/Windows/Fonts/simsun.ttc")


async def test_selected_font_flows_through_real_graph_and_renderer(tmp_path):
    from uuid import uuid4
    from tests.agent.test_controlled_design import executor
    agent = executor()
    try:
        outcome = await agent.start(PosterBrief(title="摄影社招新", title_font="mashanzheng"), run_id=uuid4(), run_directory=tmp_path)
        assert outcome.checkpoint.analysis.text_facts[0].font_name == "Ma Shan Zheng Regular"
        assert outcome.checkpoint.layout["elements"][0]["font_family"] == "open-mashanzheng"
    finally:
        await agent.aclose()
