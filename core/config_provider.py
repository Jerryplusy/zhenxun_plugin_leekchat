from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from zhenxun.configs.config import Config

from ..configs import (
    DEFAULT_GROUPS_CONFIG,
    LeekchatConfig,
    PERSONALIZATION_CONFIG,
)


def _deep_merge(base: dict, overrides: dict | None) -> dict:
    if not overrides:
        return dict(base)
    out = dict(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _normalize_id_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return [int(x) for x in value if str(x).strip()]
    if isinstance(value, str):
        return [int(x.strip()) for x in value.split(",") if x.strip()]
    return []


def _normalize_media_blacklist(value: Any) -> list[int]:
    return _normalize_id_list(value)


class ChatConfigProvider:
    """构造合并后的 LeekchatConfig。"""

    def __init__(
        self,
        base_config: dict | None = None,
        settings_config: dict | None = None,
        personalization_config: dict | None = None,
    ) -> None:
        self._base = base_config or {}
        self._settings = settings_config or {}
        self._personalization = personalization_config or PERSONALIZATION_CONFIG
        self._groups: dict[str, dict] = {}
        self._cached: LeekchatConfig | None = None

    def set_groups_config(self, groups_file: dict | None) -> None:
        if not groups_file:
            self._groups = {}
            return
        self._groups = groups_file.get("groups", {}) or {}
        self._cached = None

    def invalidate(self) -> None:
        self._cached = None

    def _build(self) -> LeekchatConfig:
        merged = _deep_merge(_deep_merge(self._base, self._settings), self._personalization)
        merged = _deep_merge(merged, self._base)

        merged["blacklistGroups"] = _normalize_id_list(merged.get("blacklistGroups"))
        merged["whitelistGroups"] = _normalize_id_list(merged.get("whitelistGroups"))
        merged["mediaAnalysisBlacklistUsers"] = _normalize_media_blacklist(
            merged.get("mediaAnalysisBlacklistUsers")
        )

        return LeekchatConfig.model_validate(merged)

    def __call__(self, group_id: int | None = None) -> LeekchatConfig:
        base = self._build() if self._cached is None else self._cached
        if group_id is None:
            return base
        overrides = self._groups.get(str(group_id))
        if not overrides:
            return base
        override_dict = _deep_merge(
            base.model_dump(), overrides.model_dump() if isinstance(overrides, BaseModel) else overrides
        )
        return LeekchatConfig.model_validate(override_dict)


def read_config_from_zhenxun(module: str = "zhenxun_plugin_leekchat") -> dict:
    """从 zhenxun ConfigCache 读取所有配置键。

    keys: BASE / SETTINGS / PERSONALIZATION / GROUPS / MAIN_MODEL / WORKING_MODEL / VISION_MODEL
    """
    keys = {
        "BASE": Config.get_config(module, "BASE", "{}"),
        "SETTINGS": Config.get_config(module, "SETTINGS", "{}"),
        "PERSONALIZATION": Config.get_config(module, "PERSONALIZATION", "{}"),
        "GROUPS": Config.get_config(module, "GROUPS", "{}"),
        "MAIN_MODEL": Config.get_config(module, "MAIN_MODEL", ""),
        "WORKING_MODEL": Config.get_config(module, "WORKING_MODEL", ""),
        "VISION_MODEL": Config.get_config(module, "VISION_MODEL", ""),
    }

    import json

    def _load(value: Any, default: dict) -> dict:
        if not value:
            return default
        if isinstance(value, dict):
            return value
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else default
        except (json.JSONDecodeError, TypeError):
            return default

    return {
        "base": _load(keys["BASE"], {}),
        "settings": _load(keys["SETTINGS"], {}),
        "personalization": _load(keys["PERSONALIZATION"], PERSONALIZATION_CONFIG),
        "groups": _load(keys["GROUPS"], DEFAULT_GROUPS_CONFIG),
        "main_model": keys["MAIN_MODEL"] or "",
        "working_model": keys["WORKING_MODEL"] or "",
        "vision_model": keys["VISION_MODEL"] or "",
    }