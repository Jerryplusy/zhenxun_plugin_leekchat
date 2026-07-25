from __future__ import annotations

import asyncio


class SessionTurnScheduler:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def run(self, session_id: str, label: str, fn) -> None:
        lock = self._get_lock(session_id)
        async with lock:
            try:
                await fn()
            except Exception as e:
                from zhenxun.services.log import logger

                logger.error(f"[SessionTurnScheduler:{label}] session={session_id} error: {e}", e=e)
                raise

    def dispose(self) -> None:
        self._locks.clear()