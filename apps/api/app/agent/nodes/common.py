from typing import Any

from app.agent.state import PosterAgentState


def with_event(
    state: PosterAgentState,
    *,
    node: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [*state["events"], {"node": node, "message": message, "payload": payload or {}}]
