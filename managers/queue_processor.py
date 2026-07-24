from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.context import ChatPluginContext


@dataclass
class QueuedMessage:
    event: Any
    content: str
    user_name: str
    user_id: int
    message_id: int
    timestamp: int


class QueueProcessor:
    def __init__(self, plugin_ctx) -> None:
        self._ctx = plugin_ctx
        self._queues: dict[str, list[QueuedMessage]] = {}
        self._timers: dict[str, asyncio.TimerHandle] = {}
        self._delay_until: dict[str, int] = {}

    def collect_message(
        self,
        session_id: str,
        event: Any,
        content: str,
        user_name: str,
        user_id: int,
        message_id: int,
    ) -> None:
        queue = self._queues.setdefault(session_id, [])
        queue.append(
            QueuedMessage(
                event=event,
                content=content,
                user_name=user_name,
                user_id=user_id,
                message_id=message_id,
                timestamp=int(time.time() * 1000),
            )
        )

    def start_delay_timer(self, session_id: str, delay_ms: int) -> None:
        if session_id in self._timers:
            self._timers[session_id].cancel()
        loop = asyncio.get_running_loop()
        self._delay_until[session_id] = int(time.time() * 1000) + delay_ms
        timer = loop.call_later(delay_ms / 1000, self._on_timer_fire, session_id)
        self._timers[session_id] = timer

    def _on_timer_fire(self, session_id: str) -> None:
        self._timers.pop(session_id, None)
        self._delay_until.pop(session_id, None)

    def dispose(self) -> None:
        for t in self._timers.values():
            t.cancel()
        self._timers.clear()
        self._queues.clear()
        self._delay_until.clear()