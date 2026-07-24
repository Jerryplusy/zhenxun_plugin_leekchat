from __future__ import annotations

from typing import Any

from zhenxun.configs.config import Config

from ..configs import (
    BASE_CONFIG,
    LeekchatConfig,
    PERSONALIZATION_CONFIG,
    SETTINGS_CONFIG,
    flatten_dict,
)

_LIST_FIELDS: set[str] = {
    "SETTINGS_blacklistGroups",
    "SETTINGS_whitelistGroups",
    "SETTINGS_mediaAnalysisBlacklistUsers",
    "SETTINGS_allowedExternalSkills",
    "SETTINGS_nicknames",
    "SETTINGS_webReader_allowedContentTypes",
    "PERSONALIZATION_planner_idleCheckBotIds",
    "PERSONALIZATION_emoji_characters",
    "PERSONALIZATION_emoji_stickers",
}

_ORIGINAL_KEY_CASE_MAP: dict[str, str] | None = None


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


def _coerce_list(value: Any) -> list:
    """逗号分隔字符串 -> list；纯数字项转 int，其余保持 str"""
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if str(v).strip()]
    if isinstance(value, str):
        items = [v.strip() for v in value.split(",") if v.strip()]
        if items and all(x.isdigit() for x in items):
            return [int(x) for x in items]
        return items
    return []


def _load_case_map() -> dict[str, str]:
    """从同一份 flatten_dict 派生 大写 -> 原始camelCase 映射
    """
    global _ORIGINAL_KEY_CASE_MAP
    if _ORIGINAL_KEY_CASE_MAP is not None:
        return _ORIGINAL_KEY_CASE_MAP

    case_map: dict[str, str] = {}
    for prefix, nested in (
        ("BASE", BASE_CONFIG),
        ("SETTINGS", SETTINGS_CONFIG),
        ("PERSONALIZATION", PERSONALIZATION_CONFIG),
    ):
        for flat_key, _ in flatten_dict(prefix, nested):
            case_map[flat_key.upper()] = flat_key
    for k in ("MAIN_MODEL", "WORKING_MODEL", "VISION_MODEL"):
        case_map[k] = k
    _ORIGINAL_KEY_CASE_MAP = case_map
    return case_map


def _read_flat_all(module: str = "zhenxun_plugin_leekchat") -> dict[str, Any]:
    """读取所有扁平配置项，返回 原始key -> value"""
    flat: dict[str, Any] = {}
    cache = getattr(Config, "_data", None)
    if cache and module in cache:
        case_map = _load_case_map()
        for upper_key, cfg in cache[module].configs.items():
            value = cfg.value if cfg.value is not None else cfg.default_value
            flat[case_map.get(upper_key, upper_key)] = value

    # list 字段后处理
    for key in list(flat.keys()):
        leaf = key.rsplit("_", 1)[-1]
        if leaf in ("examples", "multipleStyles"):
            # 长文本列表：换行分隔
            v = flat[key]
            if isinstance(v, str):
                flat[key] = [line for line in v.split("\n") if line.strip()]
            elif not isinstance(v, list):
                flat[key] = []
        elif key in _LIST_FIELDS:
            flat[key] = _coerce_list(flat[key])
    return flat


def _unflatten(prefix: str, flat: dict[str, Any]) -> dict:
    """反扁平化：BASE_maxContextTokens -> {maxContextTokens: v}
    """
    result: dict = {}
    p = prefix + "_"
    for full_key, value in flat.items():
        if not full_key.startswith(p):
            continue
        if value is None or (isinstance(value, str) and value == ""):
            continue
        parts = full_key[len(p):].split("_")
        cursor = result
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                cursor[part] = value
            else:
                cursor = cursor.setdefault(part, {})
    return result


class ChatConfigProvider:
    """构造合并后的 LeekchatConfig。"""

    def __init__(
        self,
        base_config: dict | None = None,
        settings_config: dict | None = None,
        personalization_config: dict | None = None,
    ) -> None:
        self._base_override = base_config or {}
        self._settings_override = settings_config or {}
        self._personalization_override = personalization_config or {}
        self._cached: LeekchatConfig | None = None

    def invalidate(self) -> None:
        self._cached = None

    def _build(self) -> LeekchatConfig:
        flat = _read_flat_all()
        base = _deep_merge(BASE_CONFIG, _unflatten("BASE", flat))
        settings = _deep_merge(SETTINGS_CONFIG, _unflatten("SETTINGS", flat))
        personalization = _deep_merge(
            PERSONALIZATION_CONFIG, _unflatten("PERSONALIZATION", flat)
        )

        base = _deep_merge(base, self._base_override)
        settings = _deep_merge(settings, self._settings_override)
        personalization = _deep_merge(personalization, self._personalization_override)

        merged = _deep_merge(base, settings)
        merged = _deep_merge(merged, personalization)

        merged["blacklistGroups"] = _normalize_id_list(merged.get("blacklistGroups"))
        merged["whitelistGroups"] = _normalize_id_list(merged.get("whitelistGroups"))
        merged["mediaAnalysisBlacklistUsers"] = _normalize_id_list(
            merged.get("mediaAnalysisBlacklistUsers")
        )
        return LeekchatConfig.model_validate(merged)

    def __call__(self, group_id: int | None = None) -> LeekchatConfig:
        if self._cached is None:
            self._cached = self._build()
        return self._cached


def read_config_from_zhenxun(module: str = "zhenxun_plugin_leekchat") -> dict:
    """从 zhenxun ConfigCache 读取所有配置键"""
    flat = _read_flat_all(module)
    return {
        "base": _deep_merge(BASE_CONFIG, _unflatten("BASE", flat)),
        "settings": _deep_merge(SETTINGS_CONFIG, _unflatten("SETTINGS", flat)),
        "personalization": _deep_merge(
            PERSONALIZATION_CONFIG, _unflatten("PERSONALIZATION", flat)
        ),
        "main_model": str(flat.get("MAIN_MODEL") or ""),
        "working_model": str(flat.get("WORKING_MODEL") or ""),
        "vision_model": str(flat.get("VISION_MODEL") or ""),
    }