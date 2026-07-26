from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from zhenxun.services.ai.tools.core import FunctionTool

from .info import build_info_tools
from .permissions import ToolPermission, ToolScope, check_runtime_permission
from .web import build_web_read_page_tool, build_web_search_tool

if TYPE_CHECKING:
    from .context import ToolContext


def _to_framework_tool(raw_tool: dict[str, Any], tool_ctx: "ToolContext") -> FunctionTool:
    handler = raw_tool["handler"]
    min_perm = raw_tool.get("min_permission", ToolPermission.MEMBER)
    name = raw_tool.get("name", "")

    async def invoke(**kwargs: Any) -> Any:
        if not await check_runtime_permission(tool_ctx, min_perm):
            return {
                "success": False,
                "error": f"权限不足：工具 '{name}' 需要 {min_perm.name} 权限",
            }
        result = handler(kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    tool = FunctionTool(
        invoke,
        name=name,
        description=raw_tool.get("description", ""),
    )
    tool._base_schema = raw_tool.get(
        "parameters", {"type": "object", "properties": {}, "required": []}
    )
    tool._schema_built = True
    return tool


def _filter_tools(
    tools: list[dict], tool_ctx: "ToolContext"
) -> list[dict]:
    is_private_chat = getattr(tool_ctx, "group_id", None) is None
    user_perm: ToolPermission = getattr(
        tool_ctx, "user_permission", ToolPermission.MEMBER
    )
    filtered: list[dict] = []
    for t in tools:
        scope = t.get("scope", ToolScope.ALL)
        min_perm = t.get("min_permission", ToolPermission.MEMBER)

        if is_private_chat and scope == ToolScope.GROUP:
            continue
        if not is_private_chat and scope == ToolScope.PRIVATE:
            continue
        if user_perm < min_perm:
            continue

        filtered.append(t)
    return filtered


def build_tools(tool_ctx: "ToolContext") -> dict:
    chat_tools = build_info_tools(tool_ctx)

    config = getattr(tool_ctx, "config", None)
    if config is not None:
        searxng_enabled = getattr(getattr(config, "searxng", None), "enabled", False)
        if searxng_enabled:
            chat_tools.append(build_web_search_tool(tool_ctx))
        web_reader_enabled = getattr(getattr(config, "webReader", None), "enabled", False)
        if web_reader_enabled:
            chat_tools.append(build_web_read_page_tool(tool_ctx))


    filtered = _filter_tools(chat_tools, tool_ctx)
    return {"tools": [_to_framework_tool(t, tool_ctx) for t in filtered]}
