from __future__ import annotations

import time
from typing import TYPE_CHECKING

from zhenxun.services.log import logger
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from ..core.engine import process_chat
from ..core.media.recognition import (
    has_media_segments,
    is_group_announcement_event,
    recognize_group_media_event,
)
from ..models import ChatMessage
from ..utils import (
    extract_image_urls,
    extract_message_text,
    get_role,
    get_user_name,
    is_group_allowed,
    is_message_triggered,
)

if TYPE_CHECKING:
    from ..core.context import ChatPluginContext


async def handle_message(
    plugin_ctx: "ChatPluginContext",
    event: MessageEvent,
    bot: Bot,
) -> None:
    if getattr(event, "_ai_triggered", False):
        return

    self_id = getattr(event, "self_id", None)
    if bot is None or not self_id:
        return

    user_id = getattr(event, "user_id", None)
    if user_id == self_id:
        return

    is_group = getattr(event, "message_type", "") == "group"
    group_id = getattr(event, "group_id", None) if is_group else None

    cfg = await plugin_ctx.get_config(group_id)
    if not is_group and not getattr(cfg, "enablePrivateChat", True):
        logger.debug(
            f"[leekchat] 私聊已关闭，跳过 user={getattr(event, 'user_id', None)}"
        )
        return

    text = extract_message_text(event)
    is_group_announcement = is_group_announcement_event(event)
    media_present = has_media_segments(event)
    image_urls = extract_image_urls(event)
    if not text.strip() and not media_present and not is_group_announcement:
        return

    if group_id is not None and not is_group_allowed(group_id, cfg):
        return

    media_result = await recognize_group_media_event(plugin_ctx, event, bot, cfg)
    if media_result.announcement_handled:
        return

    chat_image_urls = image_urls
    if media_result.is_group and media_result.blocked:
        chat_image_urls = []
    elif media_result.is_group:
        chat_image_urls = []

    chat_content = text
    if media_result.image_descriptions:
        chat_content = (
            f"{text}\n\n[视觉模型识别的媒体内容]\n"
            + "\n".join(media_result.image_descriptions)
        ).strip()
        chat_image_urls = []

    if not text.strip() and not chat_image_urls and not media_result.image_descriptions:
        return

    if not is_message_triggered(event):
        logger.debug(
            f"[leekchat] 跳过 AI 回复（未触发 to_me） group={group_id} user={user_id}"
        )
        return
    if group_id is not None and not is_group_allowed(group_id, cfg):
        return

    if text.strip() == "/重置会话":

        await plugin_ctx.session_manager.reset_bot_messages(
            f"group:{group_id}" if group_id else f"personal:{user_id}"
        )
        if group_id:
            plugin_ctx.group_structured_history.clear(f"group:{group_id}")
        else:
            plugin_ctx.group_structured_history.clear(f"personal:{user_id}")
        if group_id:
            await bot.send_group_msg(
                group_id=group_id, message="已清除本会话中 AI 发送的消息~"
            )
        return

    user_name = get_user_name(event)
    user_role = get_role(event)

    session_id = f"group:{group_id}" if group_id else f"personal:{user_id}"

    if not plugin_ctx.rate_limiter.can_process(user_id, group_id, text):
        logger.info(f"[leekchat] rate-limited user={user_id}")
        return

    plugin_ctx.rate_limiter.record(user_id, group_id, text)
    if group_id:
        plugin_ctx.rate_limiter.record_interaction(group_id, user_id)

    nickname = cfg.nicknames[0] if cfg.nicknames else "Bot"
    bot_nickname = nickname

    group_name = None
    member_count = None
    if group_id:
        try:
            info = await bot.get_group_info(group_id=group_id, no_cache=True)
            group_name = getattr(info, "group_name", None)
            member_count = getattr(info, "member_count", None)
        except Exception:
            pass

    bot_role = "member"
    try:
        member = await bot.get_group_member_info(
            group_id=group_id, user_id=self_id, no_cache=True
        )
        bot_role = (getattr(member, "role", "") or "member").lower()
    except Exception:
        pass

    try:
        await plugin_ctx.session_manager.get_or_create(
            session_id,
            "group" if group_id else "personal",
            group_id if group_id else user_id,
        )
        await ChatMessage.create(
            session_id=session_id,
            role="user",
            content=chat_content,
            user_id=user_id,
            user_name=user_name,
            user_role=user_role,
            group_id=group_id,
            timestamp=int(time.time() * 1000),
            message_id=getattr(event, "message_id", None),
        )
    except Exception as e:
        logger.warning(f"[leekchat] save user message failed: {e}")

    await plugin_ctx.session_turn_scheduler.run(
        session_id,
        "message",
        lambda: process_chat(
            plugin_ctx=plugin_ctx,
            event=event,
            session_id=session_id,
            group_id=group_id,
            user_id=user_id,
            content=text,
            user_name=user_name,
            user_role=user_role,
            bot=bot,
            self_id=self_id,
            bot_role=bot_role,
            bot_nickname=bot_nickname,
            group_name=group_name,
            member_count=member_count,
            media_urls=chat_image_urls,
        ),
    )
