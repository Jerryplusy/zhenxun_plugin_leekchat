from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from zhenxun.services.log import logger
from zhenxun.utils.pydantic_compat import model_dump

from ..external_skills import is_external_skill_allowed, is_skill_allowed_for_role
from ..skills.executor import execute_plugin_command
from .permissions import ToolPermission, ToolScope

if TYPE_CHECKING:
    from ...managers import SkillSessionManager
    from ..skills.registry import SkillEntry, SkillRegistry
    from .context import ToolContext

def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def _make_smart_handler(func):
    async def handler(kwargs: dict) -> dict:
        try:
            result = func(**(kwargs or {}))
            if inspect.isawaitable(result):
                result = await result
        except TypeError as e:
            return {"success": False, "error": f"参数错误: {e}"}
        except Exception as e:
            logger.error(f"[leekchat.skills] smart 工具执行失败: {e}", e=e)
            return {"success": False, "error": str(e)}
        if result is None:
            return {"success": True, "result": "执行完成（无返回值）"}
        return {"success": True, "result": _jsonable(result)}

    return handler


def _build_smart_raw_tools(entry: "SkillEntry") -> list[dict]:
    tools: list[dict] = []
    for tag in entry.smart_tools:
        parameters = (
            model_dump(tag.parameters)
            if tag.parameters is not None
            else {"type": "object", "properties": {}, "required": []}
        )
        tools.append(
            {
                "name": f"{entry.module}.{tag.name}",
                "description": tag.description or "",
                "parameters": parameters,
                "handler": _make_smart_handler(tag.func),
                "min_permission": entry.min_permission,
                "scope": ToolScope.ALL,
            }
        )
    return tools


def _build_execute_raw_tool(entry: "SkillEntry", tool_ctx: "ToolContext") -> dict:
    timeout = float(getattr(tool_ctx.config, "skillExecuteTimeout", 30) or 30)

    async def handler(kwargs: dict) -> dict:
        command = str((kwargs or {}).get("command", "")).strip()
        if not command:
            return {"success": False, "error": "command 不能为空"}
        mode = str((kwargs or {}).get("mode", "send")).strip() or "send"
        if mode not in ("send", "quiet"):
            mode = "send"
        return await execute_plugin_command(
            tool_ctx, command, mode=mode, timeout=timeout
        )

    return {
        "name": f"{entry.module}.execute",
        "description": (
            f"Run a command of the '{entry.name}' plugin as the triggering user. "
            f"Use the exact command text from the usage doc returned by load_skill (no prefix). "
            f"mode controls reply delivery: 'send' posts the reply to chat and copies it to you "
            f"(use for actions on the user's behalf); 'quiet' intercepts the reply so only you "
            f"see it (use for queries/lists/details to avoid flooding chat, then summarize)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Full command text as it appears in the plugin's usage doc.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["send", "quiet"],
                    "description": "'send' (default) posts to chat; 'quiet' intercepts so only you see it.",
                },
            },
            "required": ["command"],
        },
        "handler": handler,
        "min_permission": entry.min_permission,
        "scope": ToolScope.ALL,
    }


def build_skill_raw_tools(entry: "SkillEntry", tool_ctx: "ToolContext") -> list[dict]:
    if entry.kind == "smart":
        return _build_smart_raw_tools(entry)
    return [_build_execute_raw_tool(entry, tool_ctx)]


def build_load_skill_tool(
    tool_ctx: "ToolContext",
    registry: "SkillRegistry",
    skill_manager: "SkillSessionManager",
) -> dict:
    async def handler(kwargs: dict) -> dict:
        skill_name = str((kwargs or {}).get("skill_name", "")).strip()
        entry = registry.resolve(skill_name)
        if entry is None:
            return {
                "success": False,
                "error": f"Skill '{skill_name}' not found. Use one of the names from the catalog in your system prompt.",
            }
        if not is_external_skill_allowed(tool_ctx.config, entry):
            return {"success": False, "error": f"Skill '{entry.name}' is not on the allowlist."}
        if not is_skill_allowed_for_role(entry, tool_ctx.user_permission):
            return {
                "success": False,
                "error": (
                    f"Permission denied: skill '{entry.name}' requires "
                    f"{entry.min_permission.name}; the triggering user does not satisfy it."
                ),
            }

        raw_tools = build_skill_raw_tools(entry, tool_ctx)
        skill_manager.load_skill(
            tool_ctx.session_id, entry.module, raw_tools, display_name=entry.name
        )

        max_chars = int(getattr(tool_ctx.config, "skillUsageMaxChars", 2000) or 2000)
        usage = entry.usage
        if len(usage) > max_chars:
            usage = usage[:max_chars] + "\n...[truncated, full usage was too long]"

        result: dict[str, Any] = {
            "success": True,
            "skill_name": entry.module,
            "display_name": entry.name,
            "description": entry.description,
            "usage": usage or "(No usage doc provided by the plugin; refer to the commands list.)",
            "tools": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                }
                for t in raw_tools
            ],
            "expires_in": "1 hour",
        }
        if entry.commands:
            result["commands"] = entry.commands
        # No hint: the execute tool's description already covers mode guidance.
        return result

    return {
        "name": "load_skill",
        "description": (
            "Load a skill from the catalog in the system prompt. Returns the plugin's usage doc "
            "and its callable tools (active for 1 hour in this session). Pass a skill name "
            "(or its module id) from the External Skills list."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Skill name from the External Skills list.",
                }
            },
            "required": ["skill_name"],
        },
        "handler": handler,
        "min_permission": ToolPermission.MEMBER,
        "scope": ToolScope.ALL,
    }
