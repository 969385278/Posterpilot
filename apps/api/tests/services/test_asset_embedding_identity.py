import httpx
import pytest
import respx

from app.providers.embedding.asset_ollama import AssetOllamaEmbeddings


@respx.mock
def test_ollama_identity_uses_digest_and_explicit_model():
    route = respx.get("http://127.0.0.1:11434/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "bge-m3:latest", "digest": "weights-v1"}]},
        )
    )
    provider = AssetOllamaEmbeddings(model="bge-m3", base_url="http://127.0.0.1:11434")
    first = provider.identity()
    assert first.endswith("bge-m3:latest:weights-v1")
    route.mock(
        return_value=httpx.Response(
            200,
            json={
                "models": [
                    {"name": "bge-m3:latest", "digest": "weights-v2"},
                ]
            },
        )
    )
    assert provider.identity() != first
    route.mock(return_value=httpx.Response(200, json={"models": []}))
    with pytest.raises(StopIteration):
        provider.identity()
