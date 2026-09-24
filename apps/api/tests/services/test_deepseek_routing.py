import json
from types import SimpleNamespace

import pytest
import respx

from app import main
from app.agent.runtime import create_vision_provider
from app.core.config import Settings
from app.providers.llm.deepseek import DeepSeekProvider
from app.providers.vision.ark import ArkVisionResponseError
from app.schemas.intent import IntentRequest
from app.services.intent_router import IntentRouter
from tests.services.test_user_memory import make_runs


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"intent": "question"}, "question"),
        ({"intent": "wrong"}, "clarify"),
        ({"intent": "generate", "brief": {"title": "invented"}}, "clarify"),
    ],
)
async def test_direct_intent_one_call_no_fake_confidence(tmp_path, payload, expected):
    runs = make_runs(tmp_path)
    runs.executor = SimpleNamespace(
        text_provider=DeepSeekProvider(
            api_key="test-key",
            model="platform-model",
            base_url="https://deepseek.test/v1",
        )
    )
    route = respx.post("https://deepseek.test/v1/chat/completions").respond(
        200,
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )
    result = await IntentRouter(runs, direct_llm=True).resolve(
        IntentRequest(text="生成一张海报，标题：春日市集"),
    )
    assert route.call_count == 1
    assert result.intent == expected
    assert result.classifier == "deepseek:platform-model"
    assert result.classifier_confidence is None
    assert result.fallback_used is False
    assert result.route_method == ("llm_direct" if expected == "question" else "unavailable")
    await runs.aclose()


@pytest.mark.asyncio
async def test_direct_missing_key_returns_clarification(tmp_path):
    runs = make_runs(tmp_path)
    runs.executor = SimpleNamespace(
        text_provider=DeepSeekProvider(
            api_key="",
            model="test",
            base_url="https://unused.test",
        )
    )
    result = await IntentRouter(runs, direct_llm=True).resolve(IntentRequest(text="生成一张海报"))
    assert result.intent == "clarify"
    assert result.route_method == "unavailable"
    assert result.classifier_confidence is None
    await runs.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_vision_reuses_deepseek_credentials_and_sends_pixels():
    settings = Settings(
        _env_file=None,
        DEEPSEEK_API_KEY="deep-key",
        ARK_API_KEY="image-key",
        DEEPSEEK_BASE_URL="https://deepseek.test/v1",
        DEEPSEEK_TEXT_MODEL="platform-model",
        VISION_PROVIDER="deepseek",
        DEEPSEEK_VISION_MODEL="",
    )
    provider = create_vision_provider(settings)
    route = respx.post("https://deepseek.test/v1/chat/completions").respond(
        200,
        json={"choices": [{"message": {"content": '{"score":80}'}}]},
    )
    assert await provider.analyze_json(image_url="data:image/png;base64,test", prompt="JSON") == {
        "score": 80
    }
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer deep-key"
    body = json.loads(request.content)
    assert body["model"] == "platform-model"
    assert body["messages"][0]["content"][1]["image_url"]["url"] == "data:image/png;base64,test"
    route.respond(400, text="unsupported image model deep-key")
    with pytest.raises(ArkVisionResponseError) as error:
        await provider.analyze_json(image_url="data:image/png;base64,test", prompt="JSON")
    assert "DeepSeek" in str(error.value) and "deep-key" not in str(error.value)
    assert (
        create_vision_provider(
            settings.model_copy(update={"deepseek_vision_model": "vision-id"})
        ).model
        == "vision-id"
    )
    assert (
        create_vision_provider(settings.model_copy(update={"vision_provider": "ark"})).api_key
        == "image-key"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["deepseek", "rules"])
async def test_production_factory_wires_intent_mode(tmp_path, mode):
    settings = Settings(_env_file=None).model_copy(
        update={
            "data_dir": tmp_path,
            "database_url": f"sqlite:///{tmp_path / 'runs.sqlite3'}",
            "langgraph_checkpoint_path": tmp_path / "graph.sqlite3",
            "intent_routing_mode": mode,
        }
    )
    runs = main._build_run_service(settings)
    assert runs.intent_router.direct_llm is (mode == "deepseek")
    assert runs.executor.evaluation.vision.provider.api_key == settings.deepseek_api_key
    await runs.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("model_controls", [None, {"arbitrary": "untrusted"}])
async def test_direct_intent_ignores_model_controls_and_keeps_local_locks(tmp_path, model_controls):
    class Provider:
        model = "test"

        async def complete_json(self, messages):
            return {"intent": "modify", "controls": model_controls}

    runs = make_runs(tmp_path)
    runs.executor = SimpleNamespace(text_provider=Provider())
    result = await IntentRouter(runs, direct_llm=True).resolve(
        IntentRequest(text="标题不透明度设为80%，时间地点位置不变")
    )
    assert result.intent == "modify"
    assert result.route_method == "llm_direct"
    assert not result.can_apply  # Missing poster affects execution, not intent.
    assert result.controls.element_goals[0].opacity == 0.8
    assert result.controls.locks[0].element_id == "event_info"
    assert result.controls.locks[0].properties == ["position"]
    await runs.aclose()
