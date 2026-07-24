from __future__ import annotations

from typing import Any


_OVERRIDABLE_SUB_OBJECTS = (
    "emoji",
    "expression",
    "retention",
    "memory",
    "topic",
    "planner",
    "audio",
    "searxng",
    "webReader",
    "dynamicDelay",
)

_OVERRIDABLE_BOOLEAN_FIELDS = (
    "enableMarkdownScreenshot",
    "enableMediaRecognition",
)

_OVERRIDABLE_ARRAY_FIELDS = ("allowedExternalSkills",)


def merge_group_overrides(base, overrides):
    if not overrides:
        return base
    result = {**(base.model_dump() if hasattr(base, "model_dump") else base)}
    for key in _OVERRIDABLE_SUB_OBJECTS:
        sub = overrides.get(key) if isinstance(overrides, dict) else getattr(overrides, key, None)
        if isinstance(sub, dict) and key in result and isinstance(result[key], dict):
            result[key] = {**result[key], **sub}
    for key in _OVERRIDABLE_BOOLEAN_FIELDS:
        val = overrides.get(key) if isinstance(overrides, dict) else getattr(overrides, key, None)
        if isinstance(val, bool):
            result[key] = val
    for key in _OVERRIDABLE_ARRAY_FIELDS:
        val = overrides.get(key) if isinstance(overrides, dict) else getattr(overrides, key, None)
        if isinstance(val, list):
            result[key] = [v for v in val if isinstance(v, str)]
    return result


def extract_group_id_from_session(session_id: str) -> int | None:
    if not session_id or not isinstance(session_id, str):
        return None
    if not session_id.startswith("group:"):
        return None
    try:
        val = int(session_id[len("group:"):])
        return val if val > 0 else None
    except ValueError:
        return None