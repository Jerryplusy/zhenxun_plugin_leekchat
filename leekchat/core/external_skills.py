from __future__ import annotations

from typing import TYPE_CHECKING

from .tools.permissions import ToolPermission

if TYPE_CHECKING:
    from .skills.registry import SkillEntry, SkillRegistry


def get_allowed_skill_name_set(config) -> set[str] | None:
    allowed = getattr(config, "allowedExternalSkills", None) or []
    names = {str(x).strip() for x in allowed if str(x).strip()}
    return names or None


def is_external_skill_allowed(config, entry: "SkillEntry") -> bool:
    if not getattr(config, "enableExternalSkills", False):
        return False
    allowed = get_allowed_skill_name_set(config)
    if allowed is None:
        return True
    return entry.module in allowed or entry.name in allowed


def is_skill_allowed_for_role(
    entry: "SkillEntry", user_permission: ToolPermission
) -> bool:
    return user_permission >= entry.min_permission


def filter_allowed_external_skills(
    config,
    registry: "SkillRegistry",
    user_permission: ToolPermission = ToolPermission.MEMBER,
) -> list[dict]:
    if not getattr(config, "enableExternalSkills", False):
        return []
    return registry.catalog(
        user_permission=user_permission,
        allowed_names=get_allowed_skill_name_set(config),
    )
