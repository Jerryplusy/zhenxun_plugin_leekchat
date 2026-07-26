from __future__ import annotations

from typing import TYPE_CHECKING

from zhenxun.services.log import logger

from .permissions import ToolPermission, ToolScope

if TYPE_CHECKING:
    from ..types import AIInstance, BotProtocol
    from .context import ToolContext


def _resolve_bot(tool_ctx: "ToolContext") -> "BotProtocol | None":
    bot = getattr(tool_ctx, "bot", None)
    if bot is not None:
        return bot
    event = getattr(tool_ctx, "event", None)
    self_id = getattr(event, "self_id", None) if event else None
    if self_id and hasattr(tool_ctx, "ctx"):
        try:
            return tool_ctx.ctx.pick_bot(self_id)
        except Exception:
            return None
    return None


async def _get_member_info(tool_ctx: "ToolContext", user_id: int) -> dict:
    bot = _resolve_bot(tool_ctx)
    if not bot or not tool_ctx.group_id:
        return {"error": "Bot or groupId unavailable"}
    try:
        info = await bot.get_group_member_info(
            group_id=tool_ctx.group_id, user_id=user_id, no_cache=True
        )
        return {
            "nickname": getattr(info, "nickname", ""),
            "card": getattr(info, "card", ""),
            "sex": getattr(info, "sex", ""),
            "age": getattr(info, "age", 0),
            "area": getattr(info, "area", ""),
            "level": getattr(info, "level", ""),
            "qq_level": getattr(info, "qq_level", 0),
            "title": getattr(info, "title", ""),
        }
    except Exception as e:
        logger.error(f"[get_group_member_info] failed: {e}", e=e)
        return {"error": f"Failed to get member info: {e}"}


async def _get_member_list(tool_ctx: "ToolContext", limit: int) -> dict:
    bot = _resolve_bot(tool_ctx)
    if not bot or not tool_ctx.group_id:
        return {"error": "Bot or groupId unavailable"}
    try:
        members = await bot.get_group_member_list(group_id=tool_ctx.group_id)
        formatted = [
            {
                "user_id": m.user_id,
                "nickname": m.card or m.nickname,
                "role": m.role,
            }
            for m in members
        ]
        capped = max(1, min(int(limit or 50), 50))
        return {
            "members": formatted[:capped],
            "total": len(formatted),
        }
    except Exception as e:
        logger.error(f"[get_group_member_list] failed: {e}", e=e)
        return {"error": f"Failed to get member list: {e}"}


async def _get_media_by_message_id(bot: "BotProtocol", message_id: int) -> dict:
    from ..media.segment import get_forward_id, get_segment_source_candidates, get_segment_type, get_segment_url

    try:
        result = await bot.call_api("get_msg", message_id=message_id)
    except Exception as e:
        return {"error": f"Failed to get message: {e}"}
    data = result if isinstance(result, dict) else {}
    msg = data.get("message") or data.get("data", {}).get("message") or []
    if not isinstance(msg, list):
        return {"error": "Invalid message format"}
    for seg in msg:
        seg_type = get_segment_type(seg)
        if seg_type == "image":
            url = get_segment_url(seg)
            if url:
                return {"kind": "image", "url": url}
        elif seg_type == "video":
            sources = get_segment_source_candidates(seg)
            if sources:
                return {"kind": "video", "sources": sources}
        elif seg_type == "forward":
            fid = get_forward_id(seg)
            if fid:
                return {"kind": "forward", "forward_id": fid}
    return {"error": "No image, video, or forward message found"}


async def _describe_video(tool_ctx: "ToolContext", video_sources: list[str]) -> dict:
    ai = getattr(tool_ctx.ai_service, "getDefault", lambda: None)()
    if ai is None:
        return {"success": False, "error": "AI instance not available"}
    video_bytes = await _download_video_bytes(video_sources)
    if not video_bytes:
        return {"success": False, "error": "Failed to download video"}
    model = (
        getattr(tool_ctx.config, "multimodalWorkingModel", None)
        or getattr(tool_ctx.config, "workingModel", None)
    )
    try:
        from zhenxun.services.ai.core.messages import TextPart, VideoPart
        from zhenxun.services.ai.core.messages.models import UserMessage

        msg = UserMessage(content=[
            TextPart(text="Describe this video's content in detail in Chinese. "
                          "Describe visible people, objects, actions, scenes, and on-screen text."),
            VideoPart(raw=video_bytes, mime_type="video/mp4"),
        ])
        resp = await ai.generate(messages=[msg], model=model)
        return {"success": True, "description": resp.text or ""}
    except Exception as e:
        logger.warning(f"[describe_video] full upload failed, fallback to frames: {e}")
        return await _describe_video_by_frames(tool_ctx, video_sources, ai, model)


async def _download_video_bytes(sources: list[str]) -> bytes | None:
    for source in sources:
        try:
            from ..media.history_media import _download_bytes
            raw = await _download_bytes(source)
            if raw:
                return raw
        except Exception:
            continue
    return None


async def _describe_video_by_frames(
    tool_ctx: "ToolContext",
    sources: list[str],
    ai: "AIInstance",
    model: str,
) -> dict:
    try:
        from ..media.history_media import VIDEO_FRAME_EXTRACTION_FALLBACK, _extract_video_frames
        frames = await _extract_video_frames(sources[0])
        if not frames:
            return {"success": True, "description": VIDEO_FRAME_EXTRACTION_FALLBACK}
        from zhenxun.services.ai.core.messages import TextPart, ImagePart
        from zhenxun.services.ai.core.messages.models import UserMessage

        content: list = [
            TextPart(text=f"These {len(frames)} frames were sampled from a video. "
                          "Describe the video's likely content in Chinese."),
        ] + [ImagePart(url=url) for url in frames]
        msg = UserMessage(content=content)
        resp = await ai.generate(messages=[msg], model=model)
        return {"success": True, "description": resp.text or ""}
    except Exception as e:
        logger.error(f"[describe_video_by_frames] failed: {e}", e=e)
        return {"success": False, "error": str(e)}


async def _handle_view_media(tool_ctx: "ToolContext", args: dict) -> dict | list:
    message_id = args.get("message_id")
    if not message_id:
        return {"error": "message_id is required"}
    bot = _resolve_bot(tool_ctx)
    if bot is None:
        return {"error": "Bot not available"}
    media = await _get_media_by_message_id(bot, int(message_id))
    if "error" in media:
        return media

    is_multimodal = bool(getattr(tool_ctx.config, "isMultimodal", False))

    if media["kind"] == "image":
        if is_multimodal:
            from zhenxun.services.ai.core.messages import TextPart, ImagePart
            return [
                TextPart(
                    text=f"The image from message #{message_id} has been attached below. "
                         "Inspect it directly to answer the user's question."
                ),
                ImagePart(url=media["url"]),
            ]
        result = await _describe_image(
            tool_ctx, media["url"],
            f"Describe the image from message #{message_id} in detail in Chinese.",
        )
        if result.get("success"):
            return {"success": True, "description": result["description"]}
        return {"error": result.get("error", "Failed to analyze image")}

    if media["kind"] == "video":
        if is_multimodal:
            return await _attach_video_to_context(tool_ctx, media["sources"], message_id)
        result = await _describe_video(tool_ctx, media["sources"])
        if result.get("success"):
            return {"success": True, "description": result["description"]}
        return {"error": result.get("error", "Failed to analyze video")}

    if media["kind"] == "forward":
        return {
            "success": True,
            "description": f"The message #{message_id} is a forwarded/combined message. "
                           f"Use its forward_id={media['forward_id']} for further processing.",
            "forward_id": media["forward_id"],
        }
    return {"error": "Unknown media kind"}


async def _attach_video_to_context(
    tool_ctx: "ToolContext",
    video_sources: list[str],
    message_id: int,
) -> dict | list:
    from ..media.history_media import VIDEO_FULL_UPLOAD_MAX_BYTES

    video_bytes = await _download_video_bytes(video_sources)
    if not video_bytes:
        return {"error": "Failed to download video"}

    if len(video_bytes) <= VIDEO_FULL_UPLOAD_MAX_BYTES:
        from zhenxun.services.ai.core.messages import TextPart, VideoPart
        return [
            TextPart(
                text=f"The video from message #{message_id} has been attached below. "
                     "Inspect it directly to answer the user's question."
            ),
            VideoPart(raw=video_bytes, mime_type="video/mp4"),
        ]

    from ..media.history_media import VIDEO_FRAME_EXTRACTION_FALLBACK, _extract_video_frames
    frames = await _extract_video_frames(video_sources[0])
    if not frames:
        return {"success": True, "description": VIDEO_FRAME_EXTRACTION_FALLBACK}
    from zhenxun.services.ai.core.messages import TextPart, ImagePart
    return [
        TextPart(
            text=f"The video from message #{message_id} is too large to attach directly. "
                 f"Extracted {len(frames)} frames are attached below. Inspect them to answer the user."
        ),
    ] + [ImagePart(url=url) for url in frames]


def _avatar_url(user_id: int) -> str:
    return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"


async def _describe_image(tool_ctx: "ToolContext", image_url: str, prompt: str) -> dict:
    ai = getattr(tool_ctx.ai_service, "getDefault", lambda: None)()
    if ai is None:
        return {"success": False, "error": "AI instance not available"}
    try:
        from zhenxun.services.ai.core.messages import LLMMessage
        from zhenxun.services.ai.core.messages.parts import ImagePart, TextPart

        msg = LLMMessage.user([TextPart(text=prompt), ImagePart(url=image_url)])
        model = (
            getattr(tool_ctx.config, "multimodalWorkingModel", None)
            or getattr(tool_ctx.config, "workingModel", None)
        )
        resp = await ai.generate(messages=[msg], model=model)
        return {"success": True, "description": resp.text or ""}
    except Exception as e:
        logger.error(f"[describe_image] failed: {e}", e=e)
        return {"success": False, "error": str(e)}


def build_info_tools(tool_ctx: "ToolContext") -> list[dict]:
    tools: list[dict] = []

    if tool_ctx.group_id:
        tools.append(
            {
                "name": "get_group_member_info",
                "description": (
                    "Get detailed info about a group member, including gender, age, "
                    "QQ rating, group level, group title, etc."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "number",
                            "description": "QQ number of the member",
                        }
                    },
                    "required": ["user_id"],
                },
                "handler": lambda args: _get_member_info(tool_ctx, int(args.get("user_id", 0))),
                "scope": ToolScope.GROUP,
                "min_permission": ToolPermission.MEMBER,
            }
        )

        tools.append(
            {
                "name": "get_group_member_list",
                "description": "Get the list of group members (returns name and role only)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "number",
                            "description": "Optional max members to return (capped at 50)",
                        }
                    },
                    "required": [],
                },
                "handler": lambda args: _get_member_list(tool_ctx, args.get("limit") or 50),
                "scope": ToolScope.GROUP,
                "min_permission": ToolPermission.MEMBER,
            }
        )

    tools.append(
        {
            "name": "view_media",
            "description": (
                "View and analyze an image, video, or forwarded message by its message ID. "
                "Use this when you need to see what's in an image or video to answer "
                "the user's question, or when you encounter media tags like [image:...], "
                "[video:...], or [forward:...] in the chat history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "number",
                        "description": (
                            "The message ID of the image, video, or forward to view. "
                            "You can get this from the message context or chat history."
                        ),
                    }
                },
                "required": ["message_id"],
            },
            "handler": lambda args: _handle_view_media(tool_ctx, args),
            "scope": ToolScope.GROUP,
            "min_permission": ToolPermission.MEMBER,
        }
    )

    tools.append(
        {
            "name": "view_member_avatar",
            "description": (
                "View and analyze a group member's QQ avatar. Use this when you need to "
                "see what someone's avatar looks like."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "number",
                        "description": "QQ number of the member",
                    }
                },
                "required": ["user_id"],
            },
            "handler": lambda args: _describe_image(
                tool_ctx,
                _avatar_url(int(args.get("user_id", 0))),
                f"Describe user {args.get('user_id')}'s QQ avatar.",
            ),
            "scope": ToolScope.GROUP,
            "min_permission": ToolPermission.MEMBER,
        }
    )

    return tools