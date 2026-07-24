from __future__ import annotations

import asyncio
import time
from typing import Any

from zhenxun.services.ai.core.messages import LLMMessage, TextPart
from zhenxun.services.ai.core.messages.parts import ImagePart
from zhenxun.services.log import logger

from ..context import ChatMessage, ChatResult, PromptCtx
from ..llm_caller import LLMCaller
from ..prompt import build_dynamic_user_context, build_static_system_prompt
from ..media import consume_complete_stream_units
from .stream import create_think_tag_stream_filter


async def run_chat(
    ai: Any,
    tool_ctx: Any,
    chat_history: list[ChatMessage],
    target_message,
    prompt_ctx,
    humanize,
    skill_manager,
    structured_history=None,
) -> ChatResult:
    """主对话循环 - 调 LLM，发送响应"""
    cfg = prompt_ctx.config if hasattr(prompt_ctx, "config") else prompt_ctx
    bot_nickname = getattr(prompt_ctx, "bot_nickname", "Bot")
    model_name = getattr(cfg, "mainModel", "") or ""

    emotion_state = await humanize.emotion_agent.refresh_if_needed(
        session_id=tool_ctx.session_id,
        bot_nickname=bot_nickname,
        chat_history=chat_history,
        target_message=target_message,
    )

    static_prompt = build_static_system_prompt(cfg, bot_nickname, allowed_skills=[])
    dynamic_ctx = PromptCtx(
        config=cfg,
        bot_nickname=bot_nickname,
        bot_role=getattr(prompt_ctx, "bot_role", "member"),
        is_group=getattr(prompt_ctx, "is_group", True),
        group_name=getattr(prompt_ctx, "group_name", None),
        member_count=getattr(prompt_ctx, "member_count", None),
        chat_history=chat_history,
        target_message=target_message,
        current_emotion=emotion_state.current if emotion_state else None,
        memory_context=getattr(prompt_ctx, "memory_context", None),
        topic_context=getattr(prompt_ctx, "topic_context", None),
        expression_context=getattr(prompt_ctx, "expression_context", None),
        planner_thoughts=getattr(prompt_ctx, "planner_thoughts", None),
        reply_context=getattr(prompt_ctx, "reply_context", None),
        review_messages=getattr(prompt_ctx, "review_messages", None),
        prompt_injections=getattr(prompt_ctx, "prompt_injections", None),
        active_skills_info=getattr(prompt_ctx, "active_skills_info", None),
    )
    dynamic_user_context = build_dynamic_user_context(dynamic_ctx)

    pending_image_urls = getattr(tool_ctx, "pending_image_urls", []) or []
    user_parts: list[Any] = [TextPart(text=f"{dynamic_user_context}\n\n---\n\n[User message]\n{target_message.content or ''}")]
    for url in pending_image_urls:
        user_parts.append(ImagePart(url=url))
    messages: list[LLMMessage] = [
        LLMMessage(role="system", content=[TextPart(text=static_prompt)]),
        LLMMessage(role="user", content=user_parts),
    ]

    logger.info(
        f"[run_chat] session={tool_ctx.session_id} user={target_message.user_name}({target_message.user_id})"
    )

    caller = LLMCaller()
    think_filter = create_think_tag_stream_filter()
    buffer = ""

    async def _on_delta(delta: str) -> None:
        nonlocal buffer
        if not delta:
            return
        buffer += think_filter["push"](delta, False)
        result = consume_complete_stream_units(buffer, False)
        for unit in result["units"]:
            buffer = result["rest"]
            unit = unit.strip()
            if not unit or unit == "---":
                continue
            text = unit.replace("[emotion:xxx]", "").strip()
            if not text:
                continue
            on_text = getattr(tool_ctx, "on_text_content", None)
            if on_text:
                await on_text(text)

    try:
        response = await caller.chat(
            model_name=model_name,
            messages=messages,
            stream=bool(getattr(cfg, "stream", True)),
            on_delta=_on_delta,
            temperature=getattr(cfg, "temperature", 0.8),
        )
    except Exception as e:
        logger.error(f"[run_chat] LLM failed: {e}", e=e)
        return ChatResult(messages=[""])

    raw_text = response.text or ""

    if getattr(cfg, "stream", True):
        tail = think_filter["push"]("", True)
        buffer += tail
        final = consume_complete_stream_units(buffer, True)
        for unit in final["units"]:
            unit = unit.strip()
            if not unit or unit == "---":
                continue
            on_text = getattr(tool_ctx, "on_text_content", None)
            if on_text:
                await on_text(unit)

    sticker = await humanize.emoji_agent.process_sticker_response(
        raw_text,
        ctx={"groupId": getattr(tool_ctx, "group_id", None)},
    )

    from ..media import split_outgoing_units

    final_messages = [u for u in split_outgoing_units(sticker.cleaned_text) if u.strip() and u.strip() != "---"]

    return ChatResult(
        messages=final_messages,
        tool_calls=[],
        emoji_path=sticker.emoji_path,
    )