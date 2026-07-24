from __future__ import annotations

from typing import Any

from .info import build_info_tools
from .web import build_recall_memory_tool, build_web_read_page_tool, build_web_search_tool


def build_tools(tool_ctx: Any) -> dict:
    chat_tools = build_info_tools(tool_ctx)

    config = getattr(tool_ctx, "config", None)
    if config is not None:
        searxng_enabled = getattr(getattr(config, "searxng", None), "enabled", False)
        if searxng_enabled:
            chat_tools.append(build_web_search_tool(tool_ctx))
        web_reader_enabled = getattr(getattr(config, "webReader", None), "enabled", False)
        if web_reader_enabled:
            chat_tools.append(build_web_read_page_tool(tool_ctx))
        if getattr(getattr(config, "memory", None), "enabled", False):
            chat_tools.append(build_recall_memory_tool(tool_ctx))

    return {"tools": chat_tools}