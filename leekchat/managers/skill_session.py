from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _LoadedSkill:
    skill_name: str
    display_name: str
    raw_tools: list[dict] = field(default_factory=list)
    loaded_at: int = 0
    expires_at: int = 0


class SkillSessionManager:
    """按会话隔离的技能加载缓存
    """

    def __init__(
        self, ttl_ms: int = 60 * 60_000, max_loaded_per_session: int = 5
    ) -> None:
        self._sessions: dict[str, dict[str, _LoadedSkill]] = {}
        self._ttl_ms = ttl_ms
        self._max_loaded = max_loaded_per_session

    def _now(self) -> int:
        return int(time.time() * 1000)

    def _alive(self, session_id: str) -> dict[str, _LoadedSkill]:
        skills = self._sessions.get(session_id)
        if not skills:
            return {}
        now = self._now()
        expired = [name for name, s in skills.items() if now > s.expires_at]
        for name in expired:
            del skills[name]
        if not skills:
            self._sessions.pop(session_id, None)
            return {}
        return skills

    def load_skill(
        self,
        session_id: str,
        skill_name: str,
        raw_tools: list[dict],
        display_name: str | None = None,
    ) -> None:
        skills = self._alive(session_id)
        if not skills:
            skills = {}
            self._sessions[session_id] = skills

        now = self._now()
        skills[skill_name] = _LoadedSkill(
            skill_name=skill_name,
            display_name=display_name or skill_name,
            raw_tools=list(raw_tools),
            loaded_at=now,
            expires_at=now + self._ttl_ms,
        )
        # 超出上限时按加载时间 LRU 淘汰
        while len(skills) > self._max_loaded:
            oldest = min(skills.values(), key=lambda s: s.loaded_at)
            del skills[oldest.skill_name]

    def unload_skill(self, session_id: str, skill_name: str) -> bool:
        skills = self._alive(session_id)
        if skill_name in skills:
            del skills[skill_name]
            return True
        return False

    def get_raw_tools(self, session_id: str) -> list[dict]:
        result: list[dict] = []
        for skill in self._alive(session_id).values():
            result.extend(skill.raw_tools)
        return result

    def is_loaded(self, session_id: str, skill_name: str) -> bool:
        return skill_name in self._alive(session_id)

    def get_active_skills_info(self, session_id: str, _is_allowed=None) -> str | None:
        skills = self._alive(session_id)
        if not skills:
            return None
        now = self._now()
        lines = ["Loaded skills (re-load via load_skill after expiry):"]
        for s in skills.values():
            remaining_min = max(0, (s.expires_at - now) // 60_000)
            lines.append(
                f"- {s.skill_name} ({s.display_name}): "
                f"{len(s.raw_tools)} tool(s), {remaining_min} min remaining"
            )
        return "\n".join(lines)

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def cleanup(self) -> None:
        for session_id in list(self._sessions.keys()):
            self._alive(session_id)

    # ---- 兼容旧接口 ----

    def get_tools(self, session_id: str) -> dict[str, Any]:
        return {t.get("name", ""): t for t in self.get_raw_tools(session_id)}

    def set_tools(self, session_id: str, tools: dict[str, Any]) -> None:
        self.load_skill(session_id, "_legacy", list(tools.values()))

    def get_active_feature_tools(self, session_id: str) -> list[str]:
        return [t.get("name", "") for t in self.get_raw_tools(session_id)]

    def get_active_feature_names(self, session_id: str) -> list[str]:
        return list(self._alive(session_id).keys())
