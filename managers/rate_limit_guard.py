from __future__ import annotations

import asyncio

from zhenxun.services.log import logger

from .rate_limiter import RateLimiter


class RateLimitGuard:
    def __init__(self, rate_limiter: RateLimiter):
        self._limiter = rate_limiter
        self._blocked = False
        self._lock = asyncio.Lock()

    def is_blocked(self) -> bool:
        return self._blocked

    async def __call__(self, request, context: dict | None = None) -> None:
        return await self.run(request, context)

    async def run(self, request, context: dict | None = None) -> None:
        if context is None:
            context = {}
        user_id = context.get("userId")
        group_id = context.get("groupId")
        label = context.get("label", "default")

        if not self._limiter.can_run_ai_request(user_id, group_id):
            logger.warning(
                f"[RateLimitGuard] skipped {label} user={user_id} group={group_id}"
            )
            self._blocked = True
            return None

        self._limiter.record_ai_request(user_id, group_id)
        try:
            result = await request()
            return result
        except Exception:
            raise
        finally:
            self._blocked = False