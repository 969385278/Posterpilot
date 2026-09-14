import asyncio
from collections import defaultdict
from uuid import UUID

from app.schemas.run import RunEvent


class EventBus:
    """In-process event fan-out for the local FastAPI deployment."""

    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[RunEvent]]] = defaultdict(set)

    def subscribe(self, run_id: UUID) -> asyncio.Queue[RunEvent]:
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: UUID, queue: asyncio.Queue[RunEvent]) -> None:
        subscribers = self._subscribers.get(run_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(run_id, None)

    async def publish(self, event: RunEvent) -> None:
        self.publish_nowait(event)

    def publish_nowait(self, event: RunEvent) -> None:
        for queue in tuple(self._subscribers.get(event.run_id, ())):
            queue.put_nowait(event)
