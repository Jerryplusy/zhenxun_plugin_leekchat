from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from zhenxun.services.log import logger

from ..core.context import TargetMessage
from ..core.engine import process_chat
from ..utils import get_role, get_user_name, is_group_allowed

if TYPE_CHECKING:
    from ..core.context import ChatPluginContext


POKE_COOLDOWN_MS = 10 * 60_000
_poke_cooldowns: dict[int, int] = {}


async def handle_poke(plugin_ctx: "ChatPluginContext", event: Any) -> None:
    bot = getattr(event, "bot", None)
    self_id = getattr(event, "self_id", None)
    if bot is None or not self_id:
        return

    target_id = getattr(event, "target_id", None)
    if target_id != self_id:
        return

    group_id = getattr(event, "group_id", None)
    if not group_id:
        return

    now = int(time.time() * 1000)
    last = _poke_cooldowns.get(group_id, 0)
    if now - last < POKE_COOLDOWN_MS:
        return
    _poke_cooldowns[group_id] = now

    cfg = await plugin_ctx.get_config(group_id)
    if not is_group_allowed(group_id, cfg):
        return

    user_id = getattr(event, "user_id", None) or getattr(event, "operator_id", None)
    user_name = "someone"
    try:
        member = await bot.get_group_member_info(group_id=group_id, user_id=user_id, no_cache=True)
        user_name = getattr(member, "card", None) or getattr(member, "nickname", None) or str(user_id)
    except Exception:
        pass

    session_id = f"group:{group_id}"
    bot_nickname = cfg.nicknames[0] if cfg.nicknames else "Bot"

    target_message = TargetMessage(
        user_name=user_name,
        user_id=user_id,
        user_role="member",
        content=f"[{user_name} poked you]",
        timestamp=now,
    )

    await plugin_ctx.session_turn_scheduler.run(
        session_id,
        "poke",
        lambda: process_chat(
            plugin_ctx=plugin_ctx,
            event=event,
            session_id=session_id,
            group_id=group_id,
            user_id=user_id,
            content=target_message.content,
            user_name=user_name,
            user_role="member",
            bot=bot,
            self_id=self_id,
            bot_role="member",
            bot_nickname=bot_nickname,
            group_name=None,
            member_count=None,
        ),
    )