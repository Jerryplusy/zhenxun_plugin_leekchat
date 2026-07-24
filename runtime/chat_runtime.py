from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger

from ..core.engine import run_chat


class ChatRuntime:
    def __init__(self, plugin_ctx) -> None:
        self._ctx = plugin_ctx

    async def generate_notice(self, options: dict) -> dict:
        return await self._execute_runtime_request(
            options,
            reply_context_type="reply",
            target_field="instruction",
        )

    async def request_information(self, options: dict) -> dict:
        return await self._execute_runtime_request(
            options,
            reply_context_type="reply",
            target_field="targetMessage",
        )

    async def _execute_runtime_request(self, options: dict, *, reply_context_type: str, target_field: str) -> dict:
        try:
            from ..core.context import TargetMessage

            cfg = await self._ctx.get_config(options.get("groupId"))
            instruction = options.get(target_field) or options.get("instruction") or options.get("targetMessage") or ""
            target_message = TargetMessage(
                user_name=options.get("userName", "system"),
                user_id=options.get("userId", 0),
                user_role=options.get("userRole", "member"),
                content=instruction,
                timestamp=int(__import__("time").time() * 1000),
            )

            tool_ctx = self._ctx.build_tool_context(
                plugin_ctx=self._ctx,
                event=options.get("event"),
                self_id=options.get("selfId", 0),
                session_id=f"group:{options.get('groupId', 0)}",
                group_id=options.get("groupId"),
                user_id=options.get("userId", 0),
                config=cfg,
                ai_service=self._ctx.ai_service,
                db=self._ctx.db,
                bot_role="member",
                target_message=target_message,
                humanize=self._ctx.humanize,
            )

            prompt_ctx = type(
                "PromptCtxShim",
                (),
                {
                    "config": cfg,
                    "bot_nickname": cfg.nicknames[0] if cfg.nicknames else "Bot",
                    "bot_role": "member",
                    "is_group": True,
                    "ai_service": self._ctx.ai_service,
                    "target_message": target_message,
                    "reply_context": {"type": reply_context_type},
                },
            )()

            result = await run_chat(
                ai=self._ctx.ai_instance,
                tool_ctx=tool_ctx,
                chat_history=[],
                target_message=target_message,
                prompt_ctx=prompt_ctx,
                humanize=self._ctx.humanize,
                skill_manager=self._ctx.skill_manager,
            )

            if options.get("send", False):
                from ..core.engine import send_ai_response

                bot = (options.get("event") or {}).bot if hasattr(options.get("event"), "bot") else None
                group_id = options.get("groupId")
                if bot and group_id:
                    await send_ai_response(bot, group_id, result.messages)

            return {
                "messages": result.messages,
                "tool_calls": result.tool_calls,
                "emoji_path": result.emoji_path,
            }
        except Exception as e:
            logger.error(f"[ChatRuntime] execution failed: {e}", e=e)
            return {"messages": [], "tool_calls": [], "emoji_path": None, "error": str(e)}