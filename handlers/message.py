from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from zhenxun.services.log import logger

from ..core.engine import process_chat
from ..core.media.image_analyzer import get_or_recognize_image
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


async def handle_message(plugin_ctx: "ChatPluginContext", event: Any, bot: Any) -> None:
    self_id = getattr(event, "self_id", None)
    if bot is None or not self_id:
        return

    user_id = getattr(event, "user_id", None)
    if user_id == self_id:
        return

    is_group = getattr(event, "message_type", "") == "group"
    group_id = getattr(event, "group_id", None) if is_group else None

    text = extract_message_text(event)
    image_urls = extract_image_urls(event)
    if not text.strip() and not image_urls:
        return

    cfg = await plugin_ctx.get_config(group_id)
    vision_model = getattr(cfg, "multimodalWorkingModel", None) or ""
    enable_recognition = getattr(cfg, "enableMediaRecognition", True)

    if image_urls:
        if enable_recognition:
            logger.info(
                f"[leekchat] 收到 {len(image_urls)} 张图片，cfg.multimodalWorkingModel={vision_model!r}"
            )
            for url in image_urls:
                try:
                    await get_or_recognize_image(
                        url,
                        vision_model,
                        bot=bot,
                        rate_limit_guard=getattr(plugin_ctx, "run_with_rate_limit_guard", None),
                        rate_limit_context={"userId": user_id, "groupId": group_id},
                    )
                except Exception as e:
                    logger.warning(f"[leekchat] 图片识别失败 url={url[:80]}: {e}")
        else:
            logger.info(
                f"[leekchat] 收到 {len(image_urls)} 张图片，跳过识别"
            )

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
            content=text,
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
            media_urls=image_urls,
        ),
    )
