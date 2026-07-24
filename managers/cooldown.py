from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.context import ChatPluginContext


@dataclass
class CooldownMessage:
    event: Any = None
    content: str = ""
    user_name: str = ""
    user_id: int = 0
    message_id: int = 0
    timestamp: int = 0
    is_direct_at: bool = False


class CooldownManager:
    def __init__(self, plugin_ctx) -> None:
        self._ctx = plugin_ctx
        self._until: dict[str, int] = {}
        self._messages: dict[str, list[CooldownMessage]] = {}
        self._timers: dict[str, asyncio.TimerHandle] = {}

    def collect_message(
        self,
        session_id: str,
        group_id: int,
        event: Any,
        content: str,
        is_direct_at: bool,
    ) -> None:
        messages = self._messages.setdefault(session_id, [])
        user_name = (
            event.sender.card
            if hasattr(event.sender, "card") and event.sender.card
            else event.sender.nickname
            if hasattr(event.sender, "nickname")
            else str(event.user_id)
        )
        messages.append(
            CooldownMessage(
                event=event,
                content=content,
                user_name=user_name,
                user_id=event.user_id,
                message_id=event.message_id,
                timestamp=int(time.time() * 1000),
                is_direct_at=is_direct_at,
            )
        )

    def is_in_cooldown(self, session_id: str) -> bool:
        return int(time.time() * 1000) < self._until.get(session_id, 0)

    async def start_cooldown_timer(
        self,
        session_id: str,
        group_id: int,
        self_id: int,
    ) -> None:
        if session_id in self._timers:
            self._timers[session_id].cancel()

        cfg = await self._ctx.get_config(group_id)
        cooldown_ms = getattr(cfg, "cooldownAfterReplyMs", 20_000) or 20_000
        loop = asyncio.get_running_loop()

        def _on_done():
            self._until.pop(session_id, None)
            self._timers.pop(session_id, None)
            collected = self._messages.pop(session_id, [])
            if not collected:
                return
            has_direct = any(m.is_direct_at for m in collected)
            from zhenxun.services.log import logger

            logger.info(
                f"[Cooldown] group {group_id} processing {len(collected)} messages (direct={has_direct})"
            )

        timer = loop.call_later(cooldown_ms / 1000, _on_done)
        self._timers[session_id] = timer
        self._until[session_id] = int(time.time() * 1000) + cooldown_ms

    def dispose(self) -> None:
        for t in self._timers.values():
            t.cancel()
        self._timers.clear()
        self._until.clear()
        self._messages.clear()