from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from zhenxun.services.ai.llm import generate as ai_generate
from zhenxun.services.log import logger

from ...models import ChatMessage
from .history_media import (
    summarize_group_notice,
    summarize_history_card,
    summarize_history_forward,
    summarize_history_video,
)
from .image_analyzer import get_or_recognize_image
from .segment import (
    get_card_data,
    get_forward_id,
    get_segment_source_candidates,
    get_segment_type,
    get_video_source_candidates_from_message,
    is_media_analysis_blocked,
)

if TYPE_CHECKING:
    from ...configs import LeekchatConfig
    from ..context import ChatPluginContext
    from ..types import BotProtocol


_MEDIA_SEGMENT_TYPES = {
    "image",
    "video",
    "forward",
    "json",
    "xml",
    "ark",
    "lightapp",
    "cardimage",
}


@dataclass(frozen=True)
class MediaRecognitionResult:
    is_group: bool = False
    blocked: bool = False
    announcement_handled: bool = False
    image_descriptions: tuple[str, ...] = ()


def _event_value(event: Any, *keys: str) -> Any:
    # `event` 在真实运行中可能是 NoneBot Event 对象或上游序列化后的 dict，
    # 双分支访问不可避免，类型无法用 Protocol 约束。
    for key in keys:
        if isinstance(event, dict):
            value = event.get(key)
        else:
            value = getattr(event, key, None)
        if value not in (None, ""):
            return value
    return None


def is_group_announcement_event(event: Any) -> bool:
    if (
        _event_value(event, "message_type") != "group"
        and not _event_value(event, "group_id")
    ):
        return False
    notice_type = _event_value(event, "notice_type", "event_type")
    sub_type = _event_value(event, "sub_type", "notice_sub_type")
    return notice_type in {"group_announce", "group_notice"} or sub_type in {
        "notice",
        "group_announce",
        "group_notice",
    }


def has_media_segments(event: Any) -> bool:
    segments = _event_value(event, "message")
    return isinstance(segments, list) and any(
        get_segment_type(segment) in _MEDIA_SEGMENT_TYPES for segment in segments
    )


def _schedule(coro, label: str) -> None:
    async def runner() -> None:
        try:
            await coro
        except Exception as e:
            logger.warning(f"[leekchat] {label}失败: {e}", e=e)

    asyncio.create_task(runner())


async def _recognize_segments(
    plugin_ctx: "ChatPluginContext",
    event: Any,
    bot: "BotProtocol",
    cfg: "LeekchatConfig",
    user_id: int,
    group_id: int,
) -> list[str]:
    segments = _event_value(event, "message")
    if not isinstance(segments, list):
        return []

    working_model = (
        getattr(cfg, "multimodalWorkingModel", None)
        or getattr(cfg, "workingModel", None)
        or ""
    )
    guard = getattr(plugin_ctx, "run_with_rate_limit_guard", None)
    context = {"userId": user_id, "groupId": group_id}
    image_descriptions: list[str] = []

    for segment in segments:
        segment_type = get_segment_type(segment)
        if segment_type == "image":
            image_urls = get_segment_source_candidates(segment)
            if image_urls:
                result = await get_or_recognize_image(
                    image_urls[0],
                    working_model,
                    bot=bot,
                    rate_limit_guard=guard,
                    rate_limit_context=context,
                )
                description = result.get("description") if result else None
                if description:
                    image_descriptions.append(str(description).strip())
        elif segment_type == "video":
            sources = get_segment_source_candidates(segment)
            if not sources:
                sources = await get_video_source_candidates_from_message(
                    bot, _event_value(event, "message_id")
                )
            if sources:
                _schedule(
                    summarize_history_video(
                        sources,
                        bot=bot,
                        ai_generate=ai_generate,
                        model_name=working_model,
                        rate_limit_guard=guard,
                        rate_limit_context=context,
                    ),
                    "视频识别",
                )
        elif segment_type == "forward":
            forward_id = get_forward_id(segment)
            if forward_id:
                _schedule(
                    summarize_history_forward(
                        forward_id,
                        bot=bot,
                        ai_generate=ai_generate,
                        working_model=working_model,
                        rate_limit_guard=guard,
                        rate_limit_context=context,
                    ),
                    "转发识别",
                )
        elif segment_type in {"json", "xml", "ark", "lightapp", "cardimage"}:
            card_data = get_card_data(segment)
            if card_data:
                _schedule(
                    summarize_history_card(
                        card_data,
                        ai_generate=ai_generate,
                        working_model=working_model,
                        rate_limit_guard=guard,
                        rate_limit_context=context,
                    ),
                    "卡片识别",
                )
    return image_descriptions


async def _recognize_announcement(
    plugin_ctx: "ChatPluginContext",
    event: Any,
    cfg: "LeekchatConfig",
    bot: "BotProtocol",
) -> None:
    group_id = int(_event_value(event, "group_id") or 0)
    user_id = int(
        _event_value(
            event,
            "user_id",
            "sender_id",
            "operator_id",
            "publisher_id",
        )
        or 0
    )
    if not group_id:
        return

    summary = await summarize_group_notice(
        event,
        ai_generate=ai_generate,
        working_model=(
            getattr(cfg, "multimodalWorkingModel", None)
            or getattr(cfg, "workingModel", None)
            or ""
        ),
        rate_limit_guard=getattr(plugin_ctx, "run_with_rate_limit_guard", None),
        rate_limit_context={"userId": user_id, "groupId": group_id},
    )
    if not summary:
        return
    await ChatMessage.create(
        session_id=f"group:{group_id}",
        role="user",
        content=summary["content"],
        user_id=summary["user_id"],
        user_name=summary["user_name"],
        user_role=summary["user_role"],
        group_id=group_id,
        timestamp=summary["timestamp"],
        message_id=summary["message_id"] or None,
    )


async def recognize_group_media_event(
    plugin_ctx: "ChatPluginContext",
    event: Any,
    bot: "BotProtocol",
    cfg: "LeekchatConfig | None" = None,
) -> MediaRecognitionResult:
    """群聊媒体识别唯一入口，统一处理开关、黑名单和所有媒体类型。"""
    if (
        _event_value(event, "message_type") != "group"
        and not _event_value(event, "group_id")
    ):
        return MediaRecognitionResult()

    group_id = int(_event_value(event, "group_id") or 0)
    user_id = int(
        _event_value(
            event,
            "user_id",
            "sender_id",
            "operator_id",
            "publisher_id",
        )
        or 0
    )
    if not group_id:
        return MediaRecognitionResult(is_group=True)
    cfg = cfg or await plugin_ctx.get_config(group_id)

    blocked = is_media_analysis_blocked(cfg, user_id)
    enabled = bool(getattr(cfg, "enableMediaRecognition", True))
    if is_group_announcement_event(event):
        if enabled and not blocked:
            await _recognize_announcement(plugin_ctx, event, cfg, bot)
        else:
            logger.info(
                f"[leekchat] 群公告跳过识别 group={group_id} user={user_id} "
                f"enabled={enabled} blocked={blocked}"
            )
        return MediaRecognitionResult(
            is_group=True,
            blocked=not enabled or blocked,
            announcement_handled=True,
        )

    if not enabled or blocked:
        if has_media_segments(event):
            logger.info(
                f"[leekchat] 群聊媒体跳过识别 group={group_id} user={user_id} "
                f"enabled={enabled} blocked={blocked}"
            )
        return MediaRecognitionResult(is_group=True, blocked=True)

    image_descriptions = await _recognize_segments(
        plugin_ctx, event, bot, cfg, user_id, group_id
    )
    return MediaRecognitionResult(
        is_group=True,
        image_descriptions=tuple(image_descriptions),
    )
