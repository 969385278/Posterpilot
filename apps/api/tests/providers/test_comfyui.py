import json
from pathlib import Path

import httpx
import pytest
import respx

from app.providers.image.comfyui import ComfyUIProvider, ComfyUIUnavailableError


@pytest.mark.asyncio
async def test_comfyui_requires_workflow_file() -> None:
    provider = ComfyUIProvider(
        base_url="http://127.0.0.1:8188",
        workflow_path=None,
    )

    with pytest.raises(ComfyUIUnavailableError, match="workflow"):
        await provider.generate("古典园林，无文字")


@pytest.mark.asyncio
@respx.mock
async def test_comfyui_injects_prompt_and_returns_view_url(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "10": {"inputs": {"text": "old prompt"}},
                "20": {"inputs": {"seed": 1}},
            }
        ),
        encoding="utf-8",
    )
    prompt_route = respx.post("http://comfy.test/prompt").mock(
        return_value=httpx.Response(200, json={"prompt_id": "prompt-123"}),
    )
    respx.get("http://comfy.test/history/prompt-123").mock(
        return_value=httpx.Response(
            200,
            json={
                "prompt-123": {
                    "outputs": {
                        "99": {
                            "images": [
                                {
                                    "filename": "poster.png",
                                    "subfolder": "demo",
                                    "type": "output",
                                }
                            ]
                        }
                    }
                }
            },
        )
    )
    provider = ComfyUIProvider(
        base_url="http://comfy.test",
        workflow_path=workflow_path,
        poll_interval_seconds=0,
        max_polls=1,
    )

    result = await provider.generate("古典园林，无文字")

    assert result.image_url == "http://comfy.test/view?filename=poster.png&type=output&subfolder=demo"
    body = json.loads(prompt_route.calls[0].request.content)
    assert body["prompt"]["10"]["inputs"]["text"] == "古典园林，无文字"


@pytest.mark.asyncio
async def test_comfyui_rejects_workflow_without_text_input(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps({"10": {"inputs": {"seed": 1}}}), encoding="utf-8")
    provider = ComfyUIProvider(
        base_url="http://127.0.0.1:8188",
        workflow_path=workflow_path,
    )

    with pytest.raises(ComfyUIUnavailableError, match="prompt input"):
        await provider.generate("古典园林，无文字")

