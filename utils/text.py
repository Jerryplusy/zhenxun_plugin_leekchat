from __future__ import annotations

import re
from typing import Any

_THINK_RE = re.compile(r"<think[\s\S]*?</think>", re.IGNORECASE)


def strip_think_blocks(text: str) -> str:
    if not text:
        return ""
    return _THINK_RE.sub("", text).strip()


def clean_markers(text: str) -> str:
    cleaned = strip_think_blocks(text)
    cleaned = re.sub(r"<Ai>\s*<think>[\s\S]*?</think></Ai>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<｜｜DSML｜｜tool_calls>[\s\S]*?</｜｜DSML｜｜tool_calls>", "", cleaned)
    cleaned = re.sub(r"<｜｜DSML｜｜invoke[^>]*>[\s\S]*?</｜｜DSML｜｜invoke>", "", cleaned)
    cleaned = re.sub(r"<｜｜DSML｜｜parameter[^>]*>[\s\S]*?</｜｜DSML｜｜parameter>", "", cleaned)
    return cleaned.strip()


def is_group_allowed(group_id: int, cfg: Any) -> bool:
    blacklist = set(cfg.blacklistGroups or [])
    whitelist = set(cfg.whitelistGroups or [])
    if whitelist:
        return int(group_id) in whitelist
    return int(group_id) not in blacklist


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