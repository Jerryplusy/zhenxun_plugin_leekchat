from __future__ import annotations

from pathlib import Path

from zhenxun.services.log import logger

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
MARKDOWN_CSS = PLUGIN_ROOT / "resources" / "markdown" / "style.css"


async def render_markdown_to_image(markdown_content: str) -> bytes | None:
    """调 zhenxun 渲染服务将 markdown 转为 PNG 字节"""
    try:
        from zhenxun.services.renderer import renderer_service

        from zhenxun.services.renderer.types import Renderable

        class MarkdownRenderable(Renderable):
            component_css = None
            is_page = True

            def __init__(self, md: str, css: str):
                self._md = md
                self._css = css

            @property
            def template_name(self) -> str:
                return "@leekchat/markdown.html"

            def get_children(self):
                return []

        css = ""
        if MARKDOWN_CSS.exists():
            css = MARKDOWN_CSS.read_text(encoding="utf-8")

        component = MarkdownRenderable(markdown_content, css)
        return await renderer_service.render(component, use_cache=False)
    except Exception as e:
        logger.error(f"[markdown_screenshot] failed: {e}", e=e)
        return None