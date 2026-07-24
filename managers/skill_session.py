from __future__ import annotations

import time
from typing import Any


class SkillSessionManager:
    """Skill 会话缓存 - TODO: 外部 Skills 不实现，仅保留接口签名。"""

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._loaded_at: dict[str, int] = {}
        self._ttl_ms = 60 * 60_000

    def get_tools(self, session_id: str) -> dict[str, Any]:
        return dict(self._tools.get(session_id, {}))

    def set_tools(self, session_id: str, tools: dict[str, Any]) -> None:
        self._tools[session_id] = dict(tools)
        self._loaded_at[session_id] = int(time.time() * 1000)

    def get_active_skills_info(self, session_id: str, _is_allowed) -> str | None:
        return None

    def get_active_feature_tools(self, session_id: str) -> list[str]:
        return []

    def get_active_feature_names(self, session_id: str) -> list[str]:
        return []

    def cleanup(self) -> None:
        now = int(time.time() * 1000)
        expired = [sid for sid, ts in self._loaded_at.items() if now - ts > self._ttl_ms]
        for sid in expired:
            self._tools.pop(sid, None)
            self._loaded_at.pop(sid, None)