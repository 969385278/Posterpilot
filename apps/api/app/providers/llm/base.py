from collections.abc import Mapping, Sequence
from typing import Any, Protocol

ChatMessage = Mapping[str, Any]


class JsonChatProvider(Protocol):
    async def complete_json(self, messages: Sequence[ChatMessage]) -> dict[str, Any]: ...
