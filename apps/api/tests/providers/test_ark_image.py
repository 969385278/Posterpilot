import base64
import json

import httpx
import pytest
import respx

from app.providers.image.ark import ArkImageProvider, ArkImageResponseError


@pytest.mark.asyncio
@respx.mock
async def test_ark_image_returns_url_and_sends_supported_reference_image() -> None:
    route = respx.post("https://ark.test/images/generations").mock(
        return_value=httpx.Response(200, json={"data": [{"url": "https://cdn.test/poster.png"}]}),
    )
    provider = ArkImageProvider(
        api_key="test-key",
        model="doubao-seedream-5-0-lite-test",
        base_url="https://ark.test",
        default_size="1080x1440",
        output_format="png",
    )

    result = await provider.generate(
        "古典园林，预留文字区域，无文字",
        reference_image_url="https://cdn.test/original.png",
    )

    assert result.image_url == "https://cdn.test/poster.png"
    body = json.loads(route.calls[0].request.content)
    assert body["image"] == "https://cdn.test/original.png"
    assert body["output_format"] == "png"


@pytest.mark.asyncio
@respx.mock
async def test_ark_image_retries_without_reference_on_validation_error() -> None:
    route = respx.post("https://ark.test/images/generations").mock(
        side_effect=[
            httpx.Response(400, json={"error": {"message": "image is not supported"}}),
            httpx.Response(200, json={"data": [{"url": "https://cdn.test/retry.png"}]}),
        ]
    )
    provider = ArkImageProvider(
        api_key="test-key",
        model="doubao-seedream-test",
        base_url="https://ark.test",
        default_size="1080x1440",
    )

    result = await provider.generate(
        "保留活动事实，重新生成无文字主视觉",
        reference_image_url="https://cdn.test/original.png",
    )

    assert result.image_url == "https://cdn.test/retry.png"
    assert len(route.calls) == 2
    assert "image" not in json.loads(route.calls[1].request.content)


@pytest.mark.asyncio
@respx.mock
async def test_ark_image_converts_base64_to_data_url() -> None:
    encoded = base64.b64encode(b"png-data").decode("ascii")
    respx.post("https://ark.test/images/generations").mock(
        return_value=httpx.Response(200, json={"data": [{"b64_json": encoded}]}),
    )
    provider = ArkImageProvider(
        api_key="test-key",
        model="doubao-seedream-test",
        base_url="https://ark.test",
        default_size="1080x1440",
    )

    result = await provider.generate("无文字主视觉")

    assert result.image_url == f"data:image/png;base64,{encoded}"


@pytest.mark.asyncio
@respx.mock
async def test_ark_image_redacts_api_key_from_error() -> None:
    respx.post("https://ark.test/images/generations").mock(
        return_value=httpx.Response(401, text="Bearer private-ark-key is invalid"),
    )
    provider = ArkImageProvider(
        api_key="private-ark-key",
        model="doubao-seedream-test",
        base_url="https://ark.test",
        default_size="1080x1440",
    )

    with pytest.raises(ArkImageResponseError) as error:
        await provider.generate("无文字主视觉")

    assert "private-ark-key" not in str(error.value)

