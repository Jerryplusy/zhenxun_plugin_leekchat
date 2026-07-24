from __future__ import annotations

import random

from .utils import safe_json_loads


def pick_reply_style(cfg) -> str:
    base_style = getattr(getattr(cfg, "replyStyle", None), "baseStyle", "") or ""
    multiple_styles = getattr(getattr(cfg, "replyStyle", None), "multipleStyles", []) or []
    probability = float(getattr(getattr(cfg, "replyStyle", None), "multipleProbability", 0) or 0)
    if not multiple_styles or probability <= 0:
        return base_style
    if random.random() < probability:
        return random.choice(multiple_styles)
    return base_style


__all__ = ["pick_reply_style", "safe_json_loads"]