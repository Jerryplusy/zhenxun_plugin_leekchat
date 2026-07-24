from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger

from ...core.web import read_web_page, search_web_with_searxng


def build_web_search_tool(tool_ctx: Any) -> dict:
    return {
        "name": "web_search",
        "description": (
            "Search the web using SearXNG. Use this for current events, external facts, "
            "documentation, or anything not in chat history. "
            "If repeated searches do not produce a useful answer after about 2-3 attempts, "
            "stop searching and give a direct reply. "
            "This tool can only be called a limited number of times per conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Alternative: list of queries; first non-empty is used.",
                },
                "limit": {
                    "type": "number",
                    "description": "Max results (clamped by config.maxLimit).",
                },
                "time_range": {
                    "type": "string",
                    "enum": ["day", "month", "year"],
                },
                "categories": {"type": "array", "items": {"type": "string"}},
                "engines": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
        "handler": lambda args: search_web_with_searxng(tool_ctx.config.searxng, args or {}),
    }


def build_web_read_page_tool(tool_ctx: Any) -> dict:
    async def handler(args):
        try:
            ai = None
            if getattr(tool_ctx.config.webReader, "useWorkingModel", True):
                ai = tool_ctx.ai_service.getDefault() if tool_ctx.ai_service else None
                if not ai:
                    return {"success": False, "error": "AI instance not available"}
            working_model = getattr(tool_ctx.config, "workingModel", None) or ""
            return await read_web_page(ai, working_model, tool_ctx.config.webReader, args or {})
        except Exception as e:
            logger.error(f"[web_read_page] failed: {e}", e=e)
            return {"success": False, "error": f"Failed to read webpage: {e}"}

    return {
        "name": "web_read_page",
        "description": (
            "Read a webpage by URL, extract its main content, and compress the content "
            "into a short, information-dense passage. Use this directly when the user "
            "already provides a URL. web_search and web_read_page are independent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "http(s) URL"},
                "render_js": {
                    "type": "boolean",
                    "description": "Set true if the page needs JavaScript rendering.",
                },
                "question": {
                    "type": "string",
                    "description": "Optional focus question.",
                },
            },
            "required": ["url"],
        },
        "handler": handler,
    }


def build_recall_memory_tool(tool_ctx: Any) -> dict:
    async def handler(args):
        return {
            "success": False,
            "error": "TODO: recall_memory not implemented (Memory feature TODO in leekchat)",
        }

    return {
        "name": "recall_memory",
        "description": (
            "Recall historical chat context. Currently TODO - the Memory feature is not "
            "implemented yet in leekchat."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Recall question"}
            },
            "required": ["question"],
        },
        "handler": handler,
    }