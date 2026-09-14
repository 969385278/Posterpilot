import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx

from app.providers.image.base import GeneratedImage


class ComfyUIUnavailableError(RuntimeError):
    pass


class ComfyUIProvider:
    def __init__(
        self,
        *,
        base_url: str,
        workflow_path: Path | str | None,
        prompt_node_id: str = "",
        prompt_input: str = "text",
        timeout_seconds: float = 90,
        poll_interval_seconds: float = 1,
        max_polls: int = 90,
    ):
        self.base_url = base_url.rstrip("/")
        self.workflow_path = Path(workflow_path) if workflow_path else None
        self.prompt_node_id = prompt_node_id
        self.prompt_input = prompt_input
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls

    async def generate(
        self,
        prompt: str,
        *,
        size: str | None = None,
        reference_image_url: str = "",
    ) -> GeneratedImage:
        del size, reference_image_url
        workflow = self._load_workflow()
        node, input_name = self._find_prompt_input(workflow)
        node["inputs"][input_name] = prompt
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": str(uuid4())},
            )
            if response.is_error:
                raise ComfyUIUnavailableError(
                    f"ComfyUI prompt request returned HTTP {response.status_code}."
                )
            try:
                prompt_id = str(response.json()["prompt_id"])
            except (KeyError, TypeError, ValueError) as error:
                raise ComfyUIUnavailableError("ComfyUI returned no prompt_id.") from error
            image_url = await self._wait_for_image(client, prompt_id)
        return GeneratedImage(image_url=image_url, provider="comfyui", model="workflow")

    def _load_workflow(self) -> dict[str, Any]:
        if self.workflow_path is None:
            raise ComfyUIUnavailableError("ComfyUI workflow file is not configured.")
        if not self.workflow_path.is_file():
            raise ComfyUIUnavailableError(f"ComfyUI workflow file is missing: {self.workflow_path}")
        try:
            workflow = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ComfyUIUnavailableError("ComfyUI workflow file is not valid JSON.") from error
        if not isinstance(workflow, dict):
            raise ComfyUIUnavailableError("ComfyUI workflow must be a JSON object.")
        return workflow

    def _find_prompt_input(self, workflow: dict[str, Any]) -> tuple[dict[str, Any], str]:
        configured = workflow.get(self.prompt_node_id) if self.prompt_node_id else None
        if _has_text_input(configured, self.prompt_input):
            return configured, self.prompt_input
        for node in workflow.values():
            for name in (self.prompt_input, "text", "prompt", "positive"):
                if _has_text_input(node, name):
                    return node, name
        raise ComfyUIUnavailableError("ComfyUI workflow has no writable prompt input.")

    async def _wait_for_image(self, client: httpx.AsyncClient, prompt_id: str) -> str:
        for attempt in range(self.max_polls):
            response = await client.get(f"{self.base_url}/history/{prompt_id}")
            if response.is_success:
                image = _first_image(response.json(), prompt_id)
                if image:
                    return _view_url(self.base_url, image)
            if attempt + 1 < self.max_polls and self.poll_interval_seconds:
                await asyncio.sleep(self.poll_interval_seconds)
        raise ComfyUIUnavailableError("ComfyUI image generation timed out.")


def _has_text_input(node: Any, name: str) -> bool:
    return isinstance(node, dict) and isinstance(node.get("inputs"), dict) and isinstance(
        node["inputs"].get(name),
        str,
    )


def _first_image(history: Any, prompt_id: str) -> dict[str, Any] | None:
    item = history.get(prompt_id) if isinstance(history, dict) else None
    outputs = item.get("outputs", {}) if isinstance(item, dict) else {}
    for output in outputs.values() if isinstance(outputs, dict) else []:
        images = output.get("images", []) if isinstance(output, dict) else []
        if images and isinstance(images[0], dict) and images[0].get("filename"):
            return images[0]
    return None


def _view_url(base_url: str, image: dict[str, Any]) -> str:
    query = {"filename": str(image["filename"]), "type": str(image.get("type", "output"))}
    if image.get("subfolder"):
        query["subfolder"] = str(image["subfolder"])
    return f"{base_url}/view?{urlencode(query)}"

