from __future__ import annotations

import asyncio
from collections import defaultdict


class MessageQueueManager:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    def get_queue_length(self, key: str) -> int:
        return self._queues[key].qsize()

    async def put(self, key: str, item) -> None:
        await self._queues[key].put(item)

    async def get(self, key: str):
        return await self._queues[key].get()

    def task_done(self, key: str) -> None:
        self._queues[key].task_done()

    def dispose(self) -> None:
        self._queues.clear()