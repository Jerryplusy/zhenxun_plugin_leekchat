from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from zhenxun.services.ai.core.models import ModelModality
from zhenxun.services.ai.llm.system.capabilities import get_model_capabilities
from zhenxun.services.log import logger

from ...models import ChatMessage, ChatSession
from ..api.group_history import fetch_group_history_messages
from .stream_parser import parse_line_markers

if TYPE_CHECKING:
    from ...configs import LeekchatConfig
    from ..context import ChatPluginContext
    from ..tools.context import ToolContext
    from ..types import BotProtocol, ChatEvent


async def get_group_history_messages(
    bot: BotProtocol | None,
    group_id: int | None,
    session_id: str,
    limit: int,
    self_id: int | None = None,
    media_config: LeekchatConfig | None = None,
    user_id: int | None = None,
) -> list[ChatMessage]:
    """优先走 OneBot API；bot 不可用时回退数据库"""
    if bot is not None and group_id:
        try:
            api_history = await fetch_group_history_messages(
                bot=bot,
                group_id=group_id,
                self_id=self_id or 0,
                limit=limit,
                media_config=media_config,
            )
            if api_history:
                return api_history
        except Exception as e:
            logger.warning(
                f"[get_group_history_messages] API fallback to DB: {e}"
            )

    if bot is not None and not group_id and user_id:
        try:
            from ..api.friend_history import fetch_friend_history_messages

            api_history = await fetch_friend_history_messages(
                bot=bot,
                user_id=user_id,
                self_id=self_id or 0,
                limit=limit,
            )
            if api_history:
                return api_history
        except Exception as e:
            logger.warning(
                f"[get_group_history_messages] friend API fallback to DB: {e}"
            )

    rows = (
        await ChatMessage.filter(session_id=session_id)
        .order_by("-timestamp")
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        ChatMessage(
            id=r.id,
            session_id=r.session_id,
            role=r.role,
            content=r.content,
            user_id=r.user_id,
            user_name=r.user_name,
            user_role=r.user_role,
            group_id=r.group_id,
            group_name=r.group_name,
            timestamp=r.timestamp,
            message_id=r.message_id,
        )
        for r in rows
    ]


async def get_group_info_data(group_id: int, fallback_name: str | None = None) -> dict:
    return {"group_name": fallback_name, "member_count": None}


async def get_humanize_contexts(
    humanize,
    session_id: str,
    user_name: str,
    history: list,
    trigger_user_id: int | None = None,
) -> dict:
    topic_context = ""
    if getattr(humanize, "topic_tracker", None):
        topic_context = humanize.topic_tracker.get_topic_context(session_id) or ""
    expression_context = ""
    if getattr(humanize, "expression_learner", None) and trigger_user_id:
        expression_context = (
            humanize.expression_learner.get_expression_context_for_user(
                trigger_user_id, user_name
            )
            or ""
        )
    return {
        "memory_context": None,
        "topic_context": topic_context or None,
        "expression_context": expression_context or None,
    }


def build_tool_context(
    plugin_ctx: "ChatPluginContext",
    event: ChatEvent,
    self_id: int,
    session_id: str,
    group_id: int | None,
    user_id: int,
    config: LeekchatConfig,
    ai_service,
    db,
    bot_role: str,
    target_message,
    humanize,
    pending_image_urls: list[str] | None = None,
) -> ToolContext:
    from ..tools.context import ToolContext
    from ..tools.permissions import compute_user_permission_sync

    user_role = getattr(target_message, "user_role", "member")

    return ToolContext(
        session_id=session_id,
        group_id=group_id,
        user_id=user_id,
        config=config,
        ai_service=ai_service,
        db=db,
        event=event,
        bot=getattr(event, "bot", None),
        trigger_skill_role="member",
        bot_role=bot_role,
        user_permission=compute_user_permission_sync(user_id, user_role),
        target_message=target_message,
        pending_image_urls=pending_image_urls or [],
    )


def build_structured_user_input_from_target(target_message) -> dict:
    return {
        "user_id": getattr(target_message, "user_id", 0),
        "user_name": getattr(target_message, "user_name", ""),
        "content": getattr(target_message, "content", ""),
        "timestamp": getattr(target_message, "timestamp", int(time.time() * 1000)),
        "message_id": getattr(target_message, "message_id", None),
    }


async def finalize_chat_turn(
    plugin_ctx: "ChatPluginContext",
    *,
    event: Any,
    bot: BotProtocol | None = None,
    cfg: LeekchatConfig,
    result,
    group_id: int | None,
    session_id: str,
    user_id: int,
    self_id: int,
    tool_ctx,
    send: bool,
    is_live: bool,
) -> None:
    from .send import send_ai_response, send_emoji

    if not send:
        return

    bot = bot or getattr(event, "bot", None)
    if bot is None:
        return

    messages = getattr(result, "messages", []) or []
    if messages:
        await send_ai_response(
            bot,
            group_id,
            messages,
            default_reply_id=getattr(tool_ctx.target_message, "message_id", None),
            user_id=user_id,
        )

    emoji_path = getattr(result, "emoji_path", None)
    if emoji_path:
        await send_emoji(bot, group_id, emoji_path, user_id=user_id)

    if messages:
        for msg in messages:
            try:
                await ChatMessage.create(
                    session_id=session_id,
                    role="assistant",
                    content=parse_line_markers(msg).clean_text,
                    user_id=self_id,
                    user_name=cfg.nicknames[0] if cfg.nicknames else "Bot",
                    user_role="member",
                    group_id=group_id,
                    timestamp=int(time.time() * 1000),
                )
            except Exception as e:
                logger.warning(f"[finalize_chat_turn] save bot message failed: {e}")

    try:
        await ChatSession.filter(id=session_id).update(
            updated_at=int(time.time() * 1000)
        )
    except Exception:
        pass


async def process_chat(
    plugin_ctx,
    event,
    session_id: str,
    group_id: int | None,
    user_id: int,
    content: str,
    user_name: str,
    user_role: str,
    bot,
    self_id: int,
    bot_role: str,
    bot_nickname: str,
    group_name: str | None,
    member_count: int | None,
    media_urls: list[str] | None = None,
) -> None:
    from ..context import TargetMessage

    target_message = TargetMessage(
        user_name=user_name,
        user_id=user_id,
        user_role=user_role,
        content=content,
        message_id=getattr(event, "message_id", None),
        timestamp=int(time.time() * 1000),
    )

    cfg = await plugin_ctx.get_config(group_id)
    history = await get_group_history_messages(
        bot=bot,
        group_id=group_id,
        session_id=session_id,
        limit=getattr(cfg, "historyCount", 100),
        self_id=self_id,
        media_config=cfg,
        user_id=user_id,
    )

    tool_ctx = build_tool_context(
        plugin_ctx,
        event,
        self_id,
        session_id,
        group_id,
        user_id,
        cfg,
        plugin_ctx.ai_service,
        plugin_ctx.db,
        bot_role,
        target_message,
        plugin_ctx.humanize,
        pending_image_urls=media_urls or [],
    )

    contexts = await get_humanize_contexts(
        plugin_ctx.humanize, session_id, user_name, history, user_id
    )

    from .run import run_chat

    async def _run_chat_with_media():
        if media_urls:
            main_model = getattr(cfg, "mainModel", "") or ""
            main_accepts_image = get_model_capabilities(
                main_model
            ).accepts_input(ModelModality.IMAGE)

            if not main_accepts_image:
                tool_ctx.pending_image_urls = []
                if not target_message.content.strip():
                    target_message.content = "[图片内容未能识别]"

        return await run_chat(
            ai=plugin_ctx.ai_instance,
            tool_ctx=tool_ctx,
            chat_history=history,
            target_message=target_message,
            prompt_ctx=type(
                "PromptCtxShim",
                (),
                {
                    "config": cfg,
                    "bot_nickname": bot_nickname,
                    "bot_role": bot_role,
                    "is_group": group_id is not None,
                    "group_name": group_name,
                    "member_count": member_count,
                    "ai_service": plugin_ctx.ai_service,
                    "memory_context": contexts.get("memory_context"),
                    "topic_context": contexts.get("topic_context"),
                    "expression_context": contexts.get("expression_context"),
                    "reply_context": {
                        "type": "reply",
                        "targetUser": user_name,
                        "targetMessage": content,
                    },
                },
            )(),
            humanize=plugin_ctx.humanize,
            skill_manager=plugin_ctx.skill_manager,
        )

    result = await plugin_ctx.run_with_rate_limit_guard(
        _run_chat_with_media,
        context={"userId": user_id, "groupId": group_id, "label": "message"},
    )

    if not result:
        return

    await finalize_chat_turn(
        plugin_ctx,
        event=event,
        bot=bot,
        cfg=cfg,
        result=result,
        group_id=group_id,
        session_id=session_id,
        user_id=user_id,
        self_id=self_id,
        tool_ctx=tool_ctx,
        send=True,
        is_live=True,
    )
