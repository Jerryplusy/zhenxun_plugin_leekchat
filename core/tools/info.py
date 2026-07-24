from __future__ import annotations

import re
from typing import Any

from zhenxun.services.log import logger


def _resolve_bot(tool_ctx):
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


async def _get_member_info(tool_ctx: Any, user_id: int) -> dict:
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


async def _get_member_list(tool_ctx: Any, limit: int) -> dict:
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


def _view_media_description(args: dict, tool_ctx: Any) -> str:
    message_id = args.get("message_id")
    return f"Analyze media from message_id={message_id}. Please describe what you see."


def _avatar_url(user_id: int) -> str:
    return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"


async def _describe_image(tool_ctx: Any, image_url: str, prompt: str) -> dict:
    ai = getattr(tool_ctx.ai_service, "getDefault", lambda: None)()
    if ai is None:
        return {"success": False, "error": "AI instance not available"}
    try:
        from zhenxun.services.ai.core.messages import LLMMessage
        from zhenxun.services.ai.core.messages.parts import ImagePart, TextPart

        msg = LLMMessage.user([TextPart(text=prompt), ImagePart(url=image_url)])
        cfg = getattr(tool_ctx.config, "multimodalWorkingModel", None)
        model = cfg or getattr(tool_ctx.config, "workingModel", None) or getattr(
            tool_ctx.config, "model", None
        )
        resp = await ai.generate(messages=[msg], model=model)
        return {"success": True, "description": resp.text or ""}
    except Exception as e:
        logger.error(f"[describe_image] failed: {e}", e=e)
        return {"success": False, "error": str(e)}


def build_info_tools(tool_ctx: Any) -> list[dict]:
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
        }
    )

    return tools