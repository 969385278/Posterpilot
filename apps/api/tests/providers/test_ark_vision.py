import httpx
import pytest
import respx

from app.providers.vision.ark import ArkVisionProvider, ArkVisionResponseError


@pytest.mark.asyncio
@respx.mock
async def test_ark_vision_sends_image_and_returns_json() -> None:
    route = respx.post("https://ark.test/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"layoutSummary":"标题清晰","regions":[]}',
                        }
                    }
                ]
            },
        )
    )
    provider = ArkVisionProvider(
        api_key="test-key",
        model="doubao-vision-test",
        base_url="https://ark.test",
    )

    result = await provider.analyze_json(
        image_url="https://cdn.test/poster.png",
        prompt="分析海报并仅返回 JSON",
    )

    assert result["layoutSummary"] == "标题清晰"
    content = route.calls[0].request.content.decode("utf-8")
    assert '"type":"image_url"' in content
    assert '"url":"https://cdn.test/poster.png"' in content
    assert '"response_format":{"type":"json_object"}' in content


@pytest.mark.asyncio
@respx.mock
async def test_ark_vision_accepts_json_inside_markdown_fence() -> None:
    respx.post("https://ark.test/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"score":82,"summary":"清晰","issues":[]}\n```'
                        }
                    }
                ]
            },
        )
    )
    provider = ArkVisionProvider(
        api_key="test-key",
        model="doubao-vision-test",
        base_url="https://ark.test",
    )

    result = await provider.analyze_json(
        image_url="https://cdn.test/poster.png",
        prompt="分析海报并仅返回 JSON",
    )

    assert result["score"] == 82


@pytest.mark.asyncio
@respx.mock
async def test_ark_vision_rejects_invalid_json_output() -> None:
    respx.post("https://ark.test/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )
    )
    provider = ArkVisionProvider(
        api_key="test-key",
        model="doubao-vision-test",
        base_url="https://ark.test",
    )

    with pytest.raises(ArkVisionResponseError, match="valid JSON object"):
        await provider.analyze_json(
            image_url="https://cdn.test/poster.png",
            prompt="分析海报",
        )
