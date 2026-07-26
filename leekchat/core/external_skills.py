from __future__ import annotations

from typing import TYPE_CHECKING

from .tools.permissions import ToolPermission

DEFAULT_HIDDEN_EXTERNAL_SKILLS = {
    "about",
    "auto_update",
    "bot_manage",
    "bot_profile",
    "broadcast",
    "chat_message_handle",
    "ban",
    "clear_data",
    "exec_sql",
    "fg_manage",
    "group_manage",
    "group_member_update",
    "group_update",
    "scheduler_admin",
    "statistics_handle",
    "llm_manager",
    "plugin_config_manager",
    "plugin_switch",
    "reload_setting",
    "request_manage",
    "set_admin",
    "super_power",
    "tag_manage",
    "ui_manager",
    "update_fg_info",
    "user_group_request",
    "withdraw",
}

if TYPE_CHECKING:
    from .skills.registry import SkillEntry, SkillRegistry


def get_allowed_skill_name_set(config) -> set[str] | None:
    allowed = getattr(config, "allowedExternalSkills", None)
    if allowed is None or allowed == "":
        return None
    if isinstance(allowed, str):
        items = allowed.split(",")
    elif isinstance(allowed, (list, tuple, set)):
        items = list(allowed)
    else:
        return None
    names = {str(x).strip() for x in items if str(x).strip()}
    return names or None


def get_hidden_skill_name_set(config) -> set[str]:
    hidden = getattr(config, "hiddenExternalSkills", None)
    if not hidden:
        return set(DEFAULT_HIDDEN_EXTERNAL_SKILLS)
    if hidden == "-":
        return set()
    if isinstance(hidden, str):
        items = hidden.split(",")
    elif isinstance(hidden, (list, tuple, set)):
        items = list(hidden)
    else:
        return set(DEFAULT_HIDDEN_EXTERNAL_SKILLS)
    return {str(x).strip() for x in items if str(x).strip()}


def is_external_skill_allowed(config, entry: "SkillEntry") -> bool:
    if not getattr(config, "enableExternalSkills", False):
        return False
    hidden = get_hidden_skill_name_set(config)
    if entry.module in hidden or entry.name in hidden:
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
        hidden_names=get_hidden_skill_name_set(config),
    )
