from __future__ import annotations

import random


def normalize_constraint_strength(value: object) -> str:
    if value in ("low", "medium", "high"):
        return value
    return "medium"


def pick_reply_style(config) -> str:
    base_style = getattr(getattr(config, "replyStyle", None), "baseStyle", "") or ""
    multiple_styles = getattr(getattr(config, "replyStyle", None), "multipleStyles", []) or []
    probability = float(getattr(getattr(config, "replyStyle", None), "multipleProbability", 0) or 0)

    if not multiple_styles or probability <= 0:
        return base_style

    if random.random() < probability:
        return random.choice(multiple_styles)
    return base_style


def normalize_emotion_name(value) -> str:
    return str(value or "").strip().lower()


def normalize_emotion_examples(value) -> list[str]:
    if not value or not isinstance(value, list):
        return []
    return [str(item or "").strip() for item in value if str(item or "").strip()]