import base64
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.exceptions import PosterPilotError
from app.datahub_demo import create_app
from app.schemas.visual_asset import AssetEdit, AssetMetadata, AssetReview, AssetSearch, AssetSource
from app.services.design_assistant import DesignAssistant
from app.services.visual_assets import VisualAssetService


def picture(color="navy", *, compression=6):
    output = io.BytesIO()
    Image.new("RGB", (64, 96), color).save(output, format="PNG", compress_level=compression)
    return base64.b64encode(output.getvalue()).decode()


def metadata(**overrides):
    return AssetMetadata(
        title="星空参考",
        description="夜空中散布星点",
        composition="顶部留白，下方集中主体",
        styles=["宁静"],
        scenarios=["campus_lecture"],
        **overrides,
    )


def source():
    return AssetSource(origin="original", creator="测试作者", rights="仅用于测试")


def approve(service, item, *, action="approve"):
    return service.review(
        item["id"],
        AssetReview(
            expected_revision=item["revision"],
            action=action,
            reviewer="测试审查",
            note="测试用途",
            rights_confirmed=True,
        ),
    )


class TestEmbeddings:
    """Explicit deterministic transport fixture; no claims about semantic model quality."""

    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


def test_upload_concurrent_dedup_pixel_identity_and_source_history(tmp_path):
    service = VisualAssetService(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: service.upload(picture(), metadata(), source()), range(4))
        )
    assert sum(not result["duplicate"] for result in results) == 1
    assert len(service.list()) == 1
    item = approve(service, results[0]["asset"])
    replacement = service.upload(picture(compression=0), metadata(), source())
    assert replacement["duplicate"] and replacement["asset"]["id"] == item["id"]
    assert replacement["asset"]["status"] == "candidate"
    assert len(replacement["asset"]["sources"]) == 2
    assert replacement["asset"]["measured"]["palette"][0]["color"] == "#000080"
    assert replacement["asset"]["metadata"] == item["metadata"]


def test_review_scope_index_version_and_withdrawal(tmp_path):
    service = VisualAssetService(tmp_path, embeddings=TestEmbeddings(), embedding_id="fixture-v1")
    item = service.upload(picture(), metadata(), source())["asset"]
    query = AssetSearch(query="不含任何匹配词", scenario="campus_lecture")
    assert service.search(query)["matches"] == []
    item = approve(service, item)
    assert service.index()["indexed"] == 1
    found = service.search(query)
    assert found["mode"] == "hybrid" and found["matches"][0]["reason"]["cosine"] == 1
    assert not service.search(query.model_copy(update={"scenario": "cultural_event"}))["matches"]
    assert found["matches"][0]["sources"][0]["creator"] == "测试作者"
    stale = item["revision"]
    item = service.edit(item["id"], AssetEdit(expected_revision=stale, metadata=metadata()))
    assert service.search(query)["matches"] == []
    with pytest.raises(PosterPilotError) as error:
        service.edit(item["id"], AssetEdit(expected_revision=stale, metadata=metadata()))
    assert error.value.code == "stale_asset"
    item = approve(service, item)
    assert service.search(query)["mode"] == "lexical_fallback"
    assert service.search(query)["matches"] == []
    service.index()
    service.embedding_id = "fixture-v2"
    assert service.search(query)["matches"] == []
    service.embedding_id = "fixture-v1"
    approve(service, item, action="withdraw")
    assert service.search(query)["matches"] == []


def test_invalid_upload_and_image_integrity_and_rights_gate(tmp_path):
    service = VisualAssetService(tmp_path)
    with pytest.raises(PosterPilotError):
        service.upload("not-base64", metadata(), source())
    with pytest.raises(PosterPilotError):
        service.upload(picture(), metadata(), source().model_copy(update={"origin": "external"}))
    item = service.upload(picture(), metadata(), source())["asset"]
    with pytest.raises(PosterPilotError):
        service.review(
            item["id"],
            AssetReview(
                expected_revision=1, action="approve", reviewer="审查", note="尚未确认使用权"
            ),
        )
    item = approve(service, item)
    service.image_path(item["id"]).write_bytes(b"corrupted")
    assert service.search(AssetSearch(query="星空"))["matches"] == []
    # Corruption must not prevent disabling the reference.
    assert approve(service, item, action="withdraw")["status"] == "withdrawn"


async def test_enrichment_is_a_proposal_and_cannot_overwrite_concurrent_edit(tmp_path):
    service = VisualAssetService(tmp_path)
    item = approve(service, service.upload(picture(), metadata(), source())["asset"])

    class Vision:
        model = "deterministic-test-vision"

        async def analyze_json(self, **kwargs):
            assert kwargs["image_url"].startswith("data:image/png;base64,")
            return metadata().model_copy(update={"title": "模型建议标题"}).model_dump(mode="json")

    enriched = await service.enrich(item["id"], item["revision"], Vision())
    assert enriched["metadata"]["title"] == "星空参考"
    assert enriched["enrichment"]["proposal"]["title"] == "模型建议标题"
    assert enriched["status"] == "candidate"

    class RacingVision(Vision):
        async def analyze_json(self, **kwargs):
            service.edit(
                item["id"], AssetEdit(expected_revision=enriched["revision"], metadata=metadata())
            )
            return await super().analyze_json(**kwargs)

    with pytest.raises(PosterPilotError) as error:
        await service.enrich(item["id"], enriched["revision"], RacingVision())
    assert error.value.code == "stale_asset"


def test_embedding_failure_is_explicit_lexical_fallback(tmp_path):
    service = VisualAssetService(tmp_path, embeddings=TestEmbeddings(), embedding_id="fixture")
    approve(service, service.upload(picture(), metadata(), source())["asset"])
    service.index()
    service.embeddings.embed_query = lambda text: [float("nan"), 0]
    result = service.search(AssetSearch(query="星空"))
    assert result["mode"] == "lexical_fallback" and result["fallback_reason"]
    assert result["matches"][0]["reason"]["cosine"] is None


def test_real_graph_receives_reviewed_references_and_persists_provenance(tmp_path):
    app = create_app(tmp_path / "demo")
    with TestClient(app) as client:
        runs = app.state.run_service
        response = client.post(
            "/api/v1/datahub/visual-assets",
            json={
                "image_base64": picture(),
                "metadata": metadata().model_dump(mode="json"),
                "source": source().model_dump(mode="json"),
            },
        )
        assert response.status_code == 201, response.text
        asset = response.json()["asset"]
        assert (
            client.post(
                f"/api/v1/datahub/visual-assets/{asset['id']}/review",
                json={
                    "expected_revision": 1,
                    "action": "approve",
                    "reviewer": "集成测试",
                    "note": "测试素材",
                    "rights_confirmed": True,
                },
            ).status_code
            == 200
        )
        seen = []
        original = runs.executor.text_provider.complete_json

        async def capture(messages):
            seen.extend(message["content"] for message in messages)
            return await original(messages)

        runs.executor.text_provider.complete_json = capture
        generated = client.post(
            "/api/v1/runs",
            json={"title": "星空讲座", "poster_type": "campus_lecture", "attention_layout": False},
        )
        assert generated.status_code == 202, generated.text
        run_id = generated.json()["id"]
        evidence = client.get(f"/api/v1/runs/{run_id}/artifacts/experience_round_0.json")
        assert evidence.status_code == 200, client.get(f"/api/v1/runs/{run_id}").text
        refs = evidence.json()["visual_asset_retrieval"]["matches"]
        assert refs[0]["asset_id"] == asset["id"]
        assert any(asset["id"] in content and "测试作者" in content for content in seen)


async def test_assistant_asset_tool_returns_only_reviewed_sources(tmp_path):
    from tests.services.test_user_memory import make_runs

    runs = make_runs(tmp_path)
    item = approve(
        runs.visual_assets, runs.visual_assets.upload(picture(), metadata(), source())["asset"]
    )
    assistant = DesignAssistant(runs)
    citations = {}
    result = await assistant._tool("search_visual_assets", "星空", {}, None, citations)
    assert result["matches"][0]["asset_id"] == item["id"]
    assert next(iter(citations.values())).source == "用户原创 · 测试作者"
    approve(runs.visual_assets, item, action="withdraw")
    assert not (await assistant._tool("search_visual_assets", "星空", {}, None, {}))["matches"]


def test_model_digest_drift_disables_old_vectors(tmp_path):
    provider = TestEmbeddings()
    provider.identity = lambda: "actual-digest-1"
    service = VisualAssetService(tmp_path, embeddings=provider)
    approve(service, service.upload(picture(), metadata(), source())["asset"])
    assert service.index()["embedding_id"] == "actual-digest-1"
    query = AssetSearch(query="unmatched-query")
    assert service.search(query)["mode"] == "hybrid"
    provider.identity = lambda: "actual-digest-2"
    assert service.search(query)["mode"] == "lexical_fallback"

    def changed_during_embedding(texts):
        provider.identity = lambda: "actual-digest-3"
        return [[1.0, 0.0] for _ in texts]

    provider.embed_documents = changed_during_embedding
    with pytest.raises(PosterPilotError) as error:
        service.index()
    assert error.value.code == "embedding_changed"
