import httpx
import pytest
import respx

from app.providers.llm.deepseek import DeepSeekProvider, ProviderResponseError


@pytest.mark.asyncio
@respx.mock
async def test_deepseek_requests_json_object_response() -> None:
    route = respx.post("https://api.deepseek.test/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"design_goal":"文化活动海报"}',
                        }
                    }
                ]
            },
        )
    )
    provider = DeepSeekProvider(
        api_key="test-secret",
        model="deepseek-test",
        base_url="https://api.deepseek.test",
    )

    result = await provider.complete_json(
        [
            {"role": "system", "content": "只输出 JSON"},
            {"role": "user", "content": "生成设计方案"},
        ]
    )

    assert result == {"design_goal": "文化活动海报"}
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer test-secret"
    body = request.content.decode("utf-8")
    assert '"model":"deepseek-test"' in body
    assert '"response_format":{"type":"json_object"}' in body


@pytest.mark.asyncio
@respx.mock
async def test_deepseek_rejects_non_json_message_content() -> None:
    respx.post("https://api.deepseek.test/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
        )
    )
    provider = DeepSeekProvider(
        api_key="test-secret",
        model="deepseek-test",
        base_url="https://api.deepseek.test",
    )

    with pytest.raises(ProviderResponseError, match="valid JSON object"):
        await provider.complete_json([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
@respx.mock
async def test_deepseek_redacts_api_key_from_error() -> None:
    respx.post("https://api.deepseek.test/chat/completions").mock(
        return_value=httpx.Response(401, text="Bearer private-api-key is invalid"),
    )
    provider = DeepSeekProvider(
        api_key="private-api-key",
        model="deepseek-test",
        base_url="https://api.deepseek.test",
    )

    with pytest.raises(ProviderResponseError) as error:
        await provider.complete_json([{"role": "user", "content": "test"}])

    assert "private-api-key" not in str(error.value)
    assert "401" in str(error.value)

