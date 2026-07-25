from __future__ import annotations

from datetime import datetime
from pathlib import Path

from zhenxun.services.log import logger

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_DIR = PLUGIN_ROOT / "resources" / "markdown"
LIGHT_CSS = MARKDOWN_DIR / "style-light.css"
DARK_CSS = MARKDOWN_DIR / "style-dark.css"
FALLBACK_CSS = MARKDOWN_DIR / "style.css"

_DAY_START_HOUR = 6
_DAY_END_HOUR = 18


def _resolve_css_for_theme(theme: str) -> Path | str:
    target = LIGHT_CSS if theme == "light" else DARK_CSS if theme == "dark" else None
    if target and target.exists():
        return target
    if FALLBACK_CSS.exists():
        return FALLBACK_CSS
    return "default"


def resolve_theme(theme: str) -> str:
    if theme in ("light", "dark"):
        return theme
    hour = datetime.now().hour
    if _DAY_START_HOUR <= hour < _DAY_END_HOUR:
        return "light"
    return "dark"


async def render_markdown_to_image(
    markdown_content: str, theme: str = "auto"
) -> bytes | None:
    try:
        from zhenxun.ui import render_markdown

        actual = resolve_theme(theme)
        style = _resolve_css_for_theme(actual)
        return await render_markdown(
            markdown_content, style=style, use_cache=False
        )
    except Exception as e:
        logger.error(f"[markdown_screenshot] failed: {e}", e=e)
        return None
