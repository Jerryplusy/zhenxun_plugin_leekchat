from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructuredUserInput:
    user_id: int = 0
    user_name: str = ""
    content: str = ""
    timestamp: int = 0
    message_id: int | None = None
    media_tags: list[str] = field(default_factory=list)


class GroupStructuredHistoryManager:
    def __init__(self) -> None:
        self._messages: dict[str, list[dict]] = {}
        self._last_touch: dict[str, int] = {}

    def get_messages(self, session_id: str, ttl_ms: int) -> list[dict]:
        self._evict_expired(ttl_ms)
        return list(self._messages.get(session_id, []))

    def append(self, session_id: str, messages: list[dict], ttl_ms: int) -> None:
        self._evict_expired(ttl_ms)
        existing = self._messages.setdefault(session_id, [])
        existing.extend(messages)
        self._last_touch[session_id] = int(time.time() * 1000)

    def touch(self, session_id: str, ttl_ms: int) -> None:
        self._last_touch[session_id] = int(time.time() * 1000)

    def clear(self, session_id: str) -> None:
        self._messages.pop(session_id, None)
        self._last_touch.pop(session_id, None)

    def _evict_expired(self, ttl_ms: int) -> None:
        now = int(time.time() * 1000)
        expired = [sid for sid, ts in self._last_touch.items() if now - ts > ttl_ms]
        for sid in expired:
            self._messages.pop(sid, None)
            self._last_touch.pop(sid, None)


def build_structured_user_inputs(items: list[StructuredUserInput]) -> list[dict]:
    out = []
    for item in items:
        out.append(
            {
                "role": "user",
                "user_id": item.user_id,
                "user_name": item.user_name,
                "content": item.content,
                "timestamp": item.timestamp,
                "message_id": item.message_id,
            }
        )
    return out


def build_structured_user_messages(structured: list[dict]) -> list[dict]:
    out = []
    for s in structured:
        out.append(
            {
                "role": "user",
                "content": s.get("content", ""),
                "user_id": s.get("user_id"),
                "user_name": s.get("user_name"),
                "timestamp": s.get("timestamp"),
                "message_id": s.get("message_id"),
            }
        )
    return out