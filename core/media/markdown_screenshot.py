from __future__ import annotations

from pathlib import Path

from zhenxun.services.log import logger

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_CSS = PLUGIN_ROOT / "resources" / "markdown" / "style.css"


async def render_markdown_to_image(markdown_content: str) -> bytes | None:
    """调 zhenxun 渲染服务将 markdown 转为 PNG 字节"""
    try:
        from zhenxun.ui import render_markdown

        style = MARKDOWN_CSS if MARKDOWN_CSS.exists() else "default"
        return await render_markdown(markdown_content, style=style, use_cache=False)
    except Exception as e:
        logger.error(f"[markdown_screenshot] failed: {e}", e=e)
        return None
