"""Per-chat sequential work queue. One task runs per chat at a time."""

import asyncio
from typing import Callable, Awaitable

from . import log


class ChatQueue:
    """Async sequential queue for a single chat."""

    def __init__(self, max_size: int = 5) -> None:
        self._queue: list[Callable[[], Awaitable[None]]] = []
        self._processing = False
        self._max_size = max_size

    def enqueue(self, work: Callable[[], Awaitable[None]]) -> bool:
        if len(self._queue) >= self._max_size:
            log.warning("queue full, discarding message")
            return False
        self._queue.append(work)
        asyncio.ensure_future(self._process_next())
        return True

    @property
    def size(self) -> int:
        return len(self._queue)

    async def _process_next(self) -> None:
        if self._processing or not self._queue:
            return
        self._processing = True
        work = self._queue.pop(0)
        try:
            await work()
        except Exception as e:
            log.warning("queue work error", str(e))
        self._processing = False
        await self._process_next()


class QueueManager:
    """Manages per-chat queues."""

    def __init__(self) -> None:
        self._queues: dict[str, ChatQueue] = {}

    def get(self, chat_id: str) -> ChatQueue:
        if chat_id not in self._queues:
            self._queues[chat_id] = ChatQueue()
        return self._queues[chat_id]
