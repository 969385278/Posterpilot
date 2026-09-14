import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.nodes.retrieve_knowledge import retrieve_generation_knowledge
from app.agent.prompts.design import build_design_messages
from app.agent.state import initial_agent_state
from app.main import create_app
from app.rag.case_repository import CaseRepository
from app.rag.models import RetrievalResult
from app.schemas.design_control import ReferenceSelection
from app.schemas.poster_case import PosterCase
from tests.agent.test_generation_nodes import _brief
from tests.poster.test_design_controls import gradient_image
from tests.poster.test_action_validator import make_layout
from app.agent.tools.react_tools import ReactToolRegistry
from app.schemas.react import ReactDecision
from app.poster.reference_adapter import apply_case_references


def case_payload(case_id="fixture-poster"):
    return {
        "id": case_id, "title": "测试配色案例", "original_title": "TEST FIXTURE", "image_asset": f"{case_id}.png",
        "styles": ["低饱和", "复古"], "scenarios": ["文化活动"],
        "features": {"palette": "蓝橙参考配色", "typography": "大字号装饰字形，具体字体不确定", "composition": "中心主体，上下信息", "hierarchy": "标题优先"},
        "palette": ["#103060", "#F09030"], "suggested_priority": ["title", "event_info"],
        "cautions": ["测试夹具，不是真实设计案例"], "status": "curated", "analysis_basis": "assistant_visual_review",
        "source": {"creator": "Fixture", "institution": "Fixture", "source_url": "https://example.org/fixture", "image_url": "https://example.org/fixture.png", "rights": "test only", "rights_url": "https://example.org/rights", "retrieved_at": "2026-09-11", "image_sha256": "0" * 64},
    }


def make_repository(tmp_path: Path, payloads=None):
    payloads = payloads or [case_payload()]
    (tmp_path / "images").mkdir(exist_ok=True)
    for payload in payloads:
        gradient_image().save(tmp_path / "images" / payload["image_asset"])
    (tmp_path / "catalog.json").write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
    return CaseRepository(tmp_path)


def test_wiki_search_and_exact_selection_share_source(tmp_path: Path):
    repository = make_repository(tmp_path)
    assert repository.list_cases(query="低饱和文化活动")[0].id == "fixture-poster"
    assert repository.list_cases(style="不存在") == []
    assert repository.list_cases(query="abcdefghijk") == []
    selected = repository.resolve_selections([ReferenceSelection(case_id="fixture-poster", aspects=["palette"])])[0]
    assert selected["selected_features"] == {"palette": "蓝橙参考配色"}
    assert selected["palette"] == ["#103060", "#F09030"]
    assert selected["suggested_priority"] == []
    assert "typography" not in selected["selected_features"]


def test_rejected_and_unreviewed_cases_cannot_be_selected(tmp_path: Path):
    pending, rejected, declined = case_payload("pending"), case_payload("rejected"), case_payload("declined")
    pending.update(status="candidate", analysis_basis="unreviewed")
    rejected["status"] = "rejected"
    declined["user_acceptance"] = "rejected"
    repository = make_repository(tmp_path, [pending, rejected, declined])
    assert repository.list_cases() == []
    with pytest.raises(ValueError, match="不存在"):
        repository.get("pending")


def test_sources_and_assets_are_validated():
    payload = case_payload()
    payload["image_asset"] = "../../secret.png"
    with pytest.raises(ValidationError):
        PosterCase.model_validate(payload)
    payload = case_payload()
    payload["analysis_basis"] = "unreviewed"
    with pytest.raises(ValidationError):
        PosterCase.model_validate(payload)


def test_ambiguous_same_dimension_from_two_cases_is_rejected(tmp_path: Path):
    repository = make_repository(tmp_path, [case_payload("first"), case_payload("second")])
    with pytest.raises(ValueError, match="一个案例"):
        repository.resolve_selections([ReferenceSelection(case_id="first", aspects=["palette"]), ReferenceSelection(case_id="second", aspects=["palette"])])


class EmptyRetriever:
    async def retrieve(self, request):
        return RetrievalResult(query=request.query, fallback_reason="vector_store_unavailable")


async def test_selected_case_survives_empty_vector_retrieval_and_reaches_prompt(tmp_path: Path, monkeypatch):
    repository = make_repository(tmp_path)
    monkeypatch.setattr("app.agent.nodes.retrieve_knowledge.CaseRepository", lambda: repository)
    brief = _brief().model_copy(update={"references": [ReferenceSelection(case_id="fixture-poster", aspects=["palette"])]})
    result = await retrieve_generation_knowledge(initial_agent_state(brief), retriever=EmptyRetriever())
    assert not result["retrieval_generation"].matches
    cases = result["selected_case_context"]
    assert cases[0]["case_id"] == "fixture-poster"
    messages = build_design_messages(brief, knowledge_text="", selected_cases=cases)
    assert "蓝橙参考配色" in messages[-1]["content"]
    assert "大字号装饰字形" not in messages[-1]["content"]


def test_case_api_uses_same_catalog_and_serves_actual_image(tmp_path: Path, monkeypatch):
    repository = make_repository(tmp_path)
    monkeypatch.setattr("app.api.routes.cases.CaseRepository", lambda: repository)
    client = TestClient(create_app())
    response = client.get("/api/v1/poster-cases?q=低饱和")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "fixture-poster"
    image = client.get("/api/v1/poster-cases/fixture-poster/image")
    assert image.content.startswith(b"\x89PNG")
    assert client.get("/api/v1/poster-cases/unknown/image").status_code == 404


async def test_agent_case_search_exposes_selected_dimensions_and_real_sources(tmp_path: Path):
    repo = make_repository(tmp_path)
    decision = ReactDecision(decision="tool_call", summary="查找低饱和参考", tool_name="search_poster_cases", arguments={"query": "低饱和", "aspects": ["palette"]})
    result = await ReactToolRegistry(EmptyRetriever(), cases=repo).execute(decision, layout=make_layout())
    observation = json.loads(result.observation)
    assert observation["cases"][0]["source_url"] == "https://example.org/fixture"
    assert observation["cases"][0]["selected_features"] == {"palette": "蓝橙参考配色"}
    assert observation["cases"][0]["render_hints"] == {}
    assert result.layout == make_layout()
    assert result.citations == []  # Case sources must not masquerade as principle cards.


@pytest.mark.parametrize("arguments", [
    {"query": " ", "aspects": ["palette"]}, {"query": "复古", "aspects": ["palette"], "path": "secret"},
    {"query": "复古", "aspects": ["palette", "palette"]}, {"query": "复古", "aspects": ["palette"], "limit": True},
])
async def test_case_tool_rejects_invalid_or_unbounded_arguments(tmp_path: Path, arguments):
    tool = ReactToolRegistry(EmptyRetriever(), cases=make_repository(tmp_path))
    with pytest.raises(ValidationError):
        await tool.execute(ReactDecision(decision="tool_call", summary="测试", tool_name="search_poster_cases", arguments=arguments), layout=make_layout())


def test_case_reference_presets_change_only_selected_dimensions(tmp_path: Path):
    payload = case_payload()
    payload.update(title_font_style="serif", composition_preset="bottom_title")
    repo = make_repository(tmp_path, [payload])
    original = make_layout()
    palette = repo.resolve_selections([ReferenceSelection(case_id="fixture-poster", aspects=["palette"])])
    unchanged, notes = apply_case_references(original, palette)
    assert unchanged == original and notes == []
    typography = repo.resolve_selections([ReferenceSelection(case_id="fixture-poster", aspects=["typography"])])
    modified, notes = apply_case_references(original, typography)
    assert next(item for item in modified.elements if item.role == "title").font_family == "reference-serif"
    assert [item.box for item in modified.elements] == [item.box for item in original.elements]
    composition = repo.resolve_selections([ReferenceSelection(case_id="fixture-poster", aspects=["composition"])])
    moved, notes = apply_case_references(original, composition)
    assert next(item for item in moved.elements if item.role == "title").box.y == 0.63
    assert [item.font_family for item in moved.elements] == [item.font_family for item in original.elements]
    assert [item.content for item in moved.elements] == [item.content for item in original.elements]
    assert next(item for item in moved.elements if item.role == "main_visual") == next(item for item in original.elements if item.role == "main_visual")


def test_real_curated_catalog_has_images_hashes_and_pending_user_acceptance():
    import hashlib
    repo = CaseRepository()
    cases = repo.list_cases(limit=100)
    assert 10 <= len(cases) <= 20
    assert all(case.analysis_basis == "assistant_visual_review" for case in cases)
    assert all(case.user_acceptance == "pending" for case in cases)
    for case in cases:
        assert hashlib.sha256(repo.image_path(case.id).read_bytes()).hexdigest() == case.source.image_sha256
        source = json.loads((repo.directory / "sources" / f"{case.id}.json").read_text(encoding="utf-8"))
        assert source["response"]["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"] == "Public domain"
