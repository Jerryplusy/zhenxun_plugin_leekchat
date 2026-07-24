from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.context import ChatPluginContext


class IdleCheckManager:
    def __init__(self, plugin_ctx) -> None:
        self._ctx = plugin_ctx
        self._last_activity: dict[int, int] = {}
        self._task: asyncio.Task | None = None
        self._check_interval_s = 60

    def record_activity(self, group_id: int) -> None:
        self._last_activity[group_id] = int(time.time() * 1000)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._check_interval_s)
                await self._check_once()
        except asyncio.CancelledError:
            return

    async def _check_once(self) -> None:
        from zhenxun.services.log import logger

        cfg = await self._ctx.get_config(None)
        planner_cfg = getattr(cfg, "planner", None)
        if not planner_cfg or not getattr(planner_cfg, "enabled", False):
            return
        threshold_ms = getattr(planner_cfg, "idleThresholdMs", 30 * 60_000)
        now = int(time.time() * 1000)
        for group_id, last_ts in list(self._last_activity.items()):
            if now - last_ts >= threshold_ms:
                logger.info(
                    f"[IdleCheck] group {group_id} idle for {(now - last_ts) / 1000:.0f}s, skipping auto reply"
                )
                self._last_activity[group_id] = now

    def dispose(self) -> None:
        self._last_activity.clear()