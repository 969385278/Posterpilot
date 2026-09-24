"""Best-effort live progress without making event delivery part of graph success."""

import asyncio
import inspect
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


def with_progress(name, function, sink):
    if sink is None:
        return function

    async def run(state):
        run_id = state.get("run_id")

        def deliver(event):
            if not run_id:
                return False
            try:
                sink(UUID(run_id), [event])
                return True
            except Exception:
                logger.warning(
                    "Live Agent progress unavailable; keep graph execution", exc_info=True
                )
                return False

        decision = state.get("react_decision")
        event_node = decision.tool_name if name == "execute_react_tool" and decision else name
        started = deliver(
            {
                "node": event_node,
                "message": f"开始执行：{event_node}",
                "phase": "started",
                "payload": {"round_number": state.get("round_number", 0)},
            }
        )
        if inspect.iscoroutinefunction(function):
            updates = await function(state)
        else:
            # Keep synchronous rendering off the SSE event loop. to_thread copies
            # LangGraph contextvars, including the human interrupt context.
            updates = await asyncio.to_thread(function, state)
        if "events" not in updates:
            return updates
        count = len(state.get("events", []))
        fresh = []
        for original in updates["events"][count:]:
            event = dict(original)
            if started and event.get("node") == event_node:
                event["_started"] = True
            if deliver(event):
                event["_streamed"] = True
            fresh.append(event)
        return {**updates, "events": [*updates["events"][:count], *fresh]}

    return run
