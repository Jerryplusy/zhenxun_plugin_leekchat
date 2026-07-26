from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..configs import LeekchatConfig

_THINK_RE = re.compile(r"<think[\s\S]*?</think>", re.IGNORECASE)


def strip_think_blocks(text: str) -> str:
    if not text:
        return ""
    return _THINK_RE.sub("", text).strip()


def clean_markers(text: str) -> str:
    cleaned = strip_think_blocks(text)
    cleaned = re.sub(
        r"<Ai>\s*<think>[\s\S]*?</think></Ai>", "", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"<｜｜DSML｜｜tool_calls>[\s\S]*?</｜｜DSML｜｜tool_calls>", "", cleaned
    )
    cleaned = re.sub(
        r"<｜｜DSML｜｜invoke[^>]*>[\s\S]*?</｜｜DSML｜｜invoke>", "", cleaned
    )
    cleaned = re.sub(
        r"<｜｜DSML｜｜parameter[^>]*>[\s\S]*?</｜｜DSML｜｜parameter>", "", cleaned
    )
    return cleaned.strip()


def sanitize_brackets(text: str) -> str:
    """清理 AI 文本中半成对方括号：整对 ``[...]`` 删除，孤立 ``[`` 自动闭合，孤立 ``]`` 删除。"""
    if not text:
        return text

    open_stack: list[int] = []
    chars: list[str] = []

    for ch in text:
        if ch == "[":
            open_stack.append(len(chars))
            chars.append(ch)
        elif ch == "]":
            if open_stack:
                open_idx = open_stack.pop()
                del chars[open_idx:]
                open_stack = [i for i in open_stack if i < open_idx]
        else:
            chars.append(ch)

    chars.extend("]" * len(open_stack))
    return "".join(chars)


def is_group_allowed(group_id: int, cfg: "LeekchatConfig") -> bool:
    blacklist = set(cfg.blacklistGroups or [])
    whitelist = set(cfg.whitelistGroups or [])
    if whitelist:
        return int(group_id) in whitelist
    return int(group_id) not in blacklist


def is_message_triggered(event: Any) -> bool:
    """群聊仅处理 NoneBot 已判定为与机器人相关的消息。"""
    if getattr(event, "message_type", "") != "group":
        return True
    return bool(getattr(event, "to_me", False))


def extract_message_text(event: Any) -> str:
    if not event:
        return ""
    raw = getattr(event, "raw_message", None) or getattr(event, "message", None)
    if isinstance(raw, str):
        return raw
    message = getattr(event, "message", None)
    if isinstance(message, list):
        parts = []
        for seg in message:
            if isinstance(seg, dict):
                if seg.get("type") == "text":
                    parts.append(seg.get("data", {}).get("text", ""))
            elif hasattr(seg, "type") and seg.type == "text":
                parts.append(getattr(seg, "text", "") or seg.data.get("text", ""))
        return "".join(parts)
    return str(raw or "")


def extract_image_urls(event: Any) -> list[str]:
    """提取 OneBot 消息中的图片 URL，供视觉模型使用。"""
    message = getattr(event, "message", None)
    if not isinstance(message, list):
        return []

    urls: list[str] = []
    for segment in message:
        if isinstance(segment, dict):
            segment_type = segment.get("type")
            data = segment.get("data") or {}
        else:
            segment_type = getattr(segment, "type", None)
            data = getattr(segment, "data", None) or {}
        if segment_type != "image" or not isinstance(data, dict):
            continue
        url = data.get("url") or data.get("file")
        if url and str(url) not in urls:
            urls.append(str(url))
    return urls


def get_user_name(event: Any) -> str:
    sender = getattr(event, "sender", None)
    if sender is not None:
        card = getattr(sender, "card", "") or ""
        nick = getattr(sender, "nickname", "") or ""
        return card or nick or str(getattr(event, "user_id", ""))
    return str(getattr(event, "user_id", ""))


def get_role(event: Any) -> str:
    sender = getattr(event, "sender", None)
    role = getattr(sender, "role", "") if sender else ""
    role = (role or "member").lower()
    if role in {"owner", "admin", "member"}:
        return role
    return "member"
