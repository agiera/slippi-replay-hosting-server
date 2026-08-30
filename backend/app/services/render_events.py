"""Tiny in-process pub/sub used to push render job status changes over SSE.

All render state transitions happen inside this process (the dispatcher and the
result-upload endpoint), so subscribers can be notified instantly instead of
polling the database.
"""
import asyncio
from collections import defaultdict


class RenderEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, job_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[job_id].add(queue)
        return queue

    def unsubscribe(self, job_id: int, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(job_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(job_id, None)

    def publish(self, job_id: int) -> None:
        for queue in list(self._subscribers.get(job_id, ())):
            queue.put_nowait(None)


render_events = RenderEventBus()
