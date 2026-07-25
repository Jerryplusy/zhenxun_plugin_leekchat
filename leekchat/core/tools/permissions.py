from __future__ import annotations

from enum import IntEnum
from typing import Any


class ToolPermission(IntEnum):
    MEMBER = 0
    ADMIN = 1
    SUPERUSER = 2


class ToolScope:
    GROUP = "group"
    PRIVATE = "private"
    ALL = "all"


def compute_user_permission_sync(user_id: int, user_role: str) -> ToolPermission:
    try:
        from nonebot import get_driver

        superusers: set[str] = get_driver().config.superusers
        if str(user_id) in superusers:
            return ToolPermission.SUPERUSER
    except Exception:
        pass
    if user_role in ("owner", "admin"):
        return ToolPermission.ADMIN
    return ToolPermission.MEMBER


async def check_runtime_permission(
    tool_ctx: Any, min_perm: ToolPermission
) -> bool:
    if min_perm == ToolPermission.MEMBER:
        return True
    bot = getattr(tool_ctx, "bot", None)
    event = getattr(tool_ctx, "event", None)
    if bot and event:
        from nonebot.permission import SUPERUSER

        if await SUPERUSER(bot, event):
            return True
    if min_perm == ToolPermission.SUPERUSER:
        return False
    target = getattr(tool_ctx, "target_message", None)
    role = getattr(target, "user_role", "member") if target else "member"
    return role in ("owner", "admin")
