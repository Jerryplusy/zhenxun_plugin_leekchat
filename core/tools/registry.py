from __future__ import annotations

import inspect
from typing import Any

from zhenxun.services.ai.tools.core import FunctionTool

from .info import build_info_tools
from .web import build_recall_memory_tool, build_web_read_page_tool, build_web_search_tool


def _to_framework_tool(raw_tool: dict[str, Any]) -> FunctionTool:
    handler = raw_tool["handler"]

    async def invoke(**kwargs: Any) -> Any:
        result = handler(kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    tool = FunctionTool(
        invoke,
        name=raw_tool["name"],
        description=raw_tool.get("description", ""),
    )
    tool._base_schema = raw_tool.get(
        "parameters", {"type": "object", "properties": {}, "required": []}
    )
    tool._schema_built = True
    return tool


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

    return {"tools": [_to_framework_tool(tool) for tool in chat_tools]}
