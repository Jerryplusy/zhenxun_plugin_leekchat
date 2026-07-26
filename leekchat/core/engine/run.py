from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from zhenxun.services.ai.core.messages import AssistantMessage, LLMMessage, TextPart
from zhenxun.services.ai.core.messages.parts import ImagePart
from zhenxun.services.ai.run.context import RunContext
from zhenxun.services.ai.tools.engine.executor import ToolExecutor
from zhenxun.services.ai.tools.engine.registry import ToolCollection
from zhenxun.services.log import logger

from ..context import ChatMessage, ChatResult, PromptCtx
from ..external_skills import filter_allowed_external_skills
from ..llm_caller import LLMCaller, strip_think_blocks
from ..media import consume_complete_stream_units
from ..prompt import build_dynamic_user_context, build_static_system_prompt
from ..skills.registry import get_skill_registry
from ..tools.registry import build_framework_tools_from_raw, build_tools
from .stream import create_think_tag_stream_filter
from .stream_parser import parse_line_markers

if TYPE_CHECKING:
    from ..tools.context import ToolContext
    from ..types import AIInstance

_LEGACY_TOOL_RE = re.compile(
    r"\[(web_search|web_read_page):([^\]]+)\]", re.IGNORECASE
)


def _strip_legacy_tool_markers(text: str) -> str:
    return _LEGACY_TOOL_RE.sub("", text or "").strip()


def _build_available_tools_section(framework_tools: list) -> str:
    if not framework_tools:
        return ""
    lines = ["## Available Tools", "You have access to the following tools:"]
    for t in framework_tools:
        name = getattr(t, "name", "?")
        desc = getattr(t, "description", "") or ""
        lines.append(f"- {name}: {desc.split(chr(10))[0].strip()}")
    return "\n".join(lines)


async def run_chat(
    ai: AIInstance,
    tool_ctx: ToolContext,
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

    framework_tools = build_tools(tool_ctx, skill_manager=skill_manager).get("tools", [])
    allowed_skills = filter_allowed_external_skills(
        cfg, get_skill_registry(), tool_ctx.user_permission
    )
    static_prompt = build_static_system_prompt(
        cfg, bot_nickname, allowed_skills=allowed_skills
    )
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
        active_skills_info=skill_manager.get_active_skills_info(tool_ctx.session_id)
        if skill_manager is not None
        else None,
    )
    dynamic_user_context = build_dynamic_user_context(dynamic_ctx)

    def _merged_tools() -> list:
        if skill_manager is None:
            return framework_tools
        skill_raw = skill_manager.get_raw_tools(tool_ctx.session_id)
        if not skill_raw:
            return framework_tools
        return framework_tools + build_framework_tools_from_raw(skill_raw, tool_ctx)

    available_tools_text = _build_available_tools_section(_merged_tools())
    user_context = dynamic_user_context
    if available_tools_text:
        user_context = f"{available_tools_text}\n\n{user_context}"

    pending_image_urls = getattr(tool_ctx, "pending_image_urls", []) or []
    user_parts: list[TextPart | ImagePart] = [
        TextPart(
            text=(
                f"{user_context}\n\n---\n\n[User message]\n"
                f"{target_message.content or ''}"
            )
        )
    ]
    for url in pending_image_urls:
        user_parts.append(ImagePart(url=url))
    messages: list[LLMMessage] = [
        LLMMessage(role="system", content=[TextPart(text=static_prompt)]),
        LLMMessage(role="user", content=user_parts),
    ]

    logger.info(
        f"[run_chat] session={tool_ctx.session_id} "
        f"user={target_message.user_name}({target_message.user_id})"
    )

    caller = LLMCaller()
    tool_executor = ToolExecutor()
    tool_context = RunContext(
        session_id=getattr(tool_ctx, "session_id", None),
        deps=tool_ctx,
    )
    tool_records: list[dict[str, Any]] = []
    think_filter = create_think_tag_stream_filter()
    buffer = ""

    async def _on_delta(delta: str) -> None:
        nonlocal buffer
        if not delta:
            return
        delta = _strip_legacy_tool_markers(delta)
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

    response = None
    for iteration in range(max(1, int(getattr(cfg, "maxIterations", 20)))):
        iteration_tools = _merged_tools()
        available_tools = ToolCollection(iteration_tools)
        try:
            response = await caller.chat(
                model_name=model_name,
                messages=messages,
                stream=bool(getattr(cfg, "stream", True)),
                on_delta=_on_delta,
                temperature=getattr(cfg, "temperature", 0.8),
                tools=iteration_tools,
                debug=bool(getattr(cfg, "debug", False)),
            )
        except Exception as e:
            logger.error(f"[run_chat] LLM failed: {e}", e=e)
            return ChatResult(messages=[""], tool_calls=tool_records)

        tool_calls = list(response.tool_calls)

        if not tool_calls:
            break

        # Preserve the exact assistant tool-call message so OpenAI-compatible
        # providers can associate every following tool result with its call ID.
        messages.append(AssistantMessage(content=list(response.content_parts)))
        try:
            tool_messages = await tool_executor.execute_batch(
                tool_calls,
                available_tools,
                context=tool_context,
            )
        except Exception as e:
            logger.error(f"[run_chat] tool execution failed: {e}", e=e)
            return ChatResult(messages=[""], tool_calls=tool_records)

        for call, tool_message in zip(tool_calls, tool_messages, strict=True):
            tool_result = (
                tool_message.tool_returns[0].output
                if tool_message.tool_returns
                else ""
            )
            tool_records.append(
                {
                    "name": call.tool_name,
                    "arguments": _parse_tool_args(call.args),
                    "result": tool_result,
                }
            )
        messages.extend(tool_messages)
    else:
        logger.warning(
            f"[run_chat] 工具调用达到上限 maxIterations={getattr(cfg, 'maxIterations', 20)}"
        )

    if response is None:
        return ChatResult(messages=[""], tool_calls=tool_records)

    raw_text = _strip_legacy_tool_markers(strip_think_blocks(response.text or ""))

    response_markers = parse_line_markers(raw_text)
    if response_markers.emotion_name:
        humanize.emotion_agent.set_emotion(
            tool_ctx.session_id, response_markers.emotion_name
        )

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

    final_messages = [
        unit
        for unit in split_outgoing_units(sticker.cleaned_text)
        if unit.strip() and unit.strip() != "---"
    ]

    return ChatResult(
        messages=final_messages,
        tool_calls=tool_records,
        emoji_path=sticker.emoji_path,
    )


def _parse_tool_args(args: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    try:
        parsed = json.loads(args)
    except (TypeError, json.JSONDecodeError):
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}
