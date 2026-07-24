from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger


def filter_allowed_external_skills(config, all_skills, trigger_role: str) -> list[dict]:
    """TODO: 外部 Skills 功能暂不实现"""
    logger.warning("TODO: filter_allowed_external_skills 未实现 - 外部 Skills 功能")
    return []


def is_external_skill_allowed(config, skill_name: str) -> bool:
    return False


def is_skill_allowed_for_role(skill, trigger_role: str) -> bool:
    return False