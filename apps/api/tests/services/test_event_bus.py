import asyncio
from uuid import uuid4

from app.schemas.run import RunEvent
from app.services.event_bus import EventBus


async def test_event_bus_delivers_published_event_to_subscriber() -> None:
    bus = EventBus()
    run_id = uuid4()
    queue = bus.subscribe(run_id)
    event = RunEvent(run_id=run_id, type="run_created", message="任务已创建")

    await bus.publish(event)

    assert await asyncio.wait_for(queue.get(), timeout=1) == event
    bus.unsubscribe(run_id, queue)
