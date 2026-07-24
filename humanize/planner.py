from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from zhenxun.services.ai.core.messages import LLMMessage, TextPart
from zhenxun.services.ai.llm import generate as ai_generate
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.log import logger


@dataclass
class PlannerResult:
    action: str
    reason: str
    wait_ms: int | None = None


class ActionPlanner:
    def __init__(self, work_ai, config_provider) -> None:
        self._work_ai = work_ai
        self._config_provider = config_provider

    async def plan(
        self,
        session_id: str,
        bot_nickname: str,
        chat_history: list,
        merged_content: str,
        is_idle_debug: bool = False,
    ) -> PlannerResult:
        cfg = self._config_provider()
        if not getattr(getattr(cfg, "planner", None), "enabled", False):
            return PlannerResult(action="reply", reason="planner disabled")

        history_lines = []
        for msg in chat_history[-20:]:
            name = msg.user_name if msg.role != "assistant" else bot_nickname
            history_lines.append(f"{name}: {msg.content}")
        history_text = "\n".join(history_lines) or "(no history)"

        prompt = (
            "You are a planner deciding whether the bot should reply in a chat. "
            "Output JSON only: {\"action\": \"reply\"|\"wait\"|\"complete\", "
            "\"reason\": \"<short>\", \"waitMs\": <int|null>}.\n\n"
            f"Bot nickname: {bot_nickname}\n"
            f"Recent chat:\n{history_text}\n\n"
            f"Latest content (idle debug={is_idle_debug}):\n{merged_content}\n"
        )
        try:
            model = getattr(cfg, "workingModel", None) or ""
            resp = await ai_generate(
                messages=[LLMMessage.user(prompt)],
                model=model,
                config=IntentBuilder().config_core(temperature=0.2, max_tokens=200),
            )
            data = json.loads((resp.text or "{}").strip())
            action = str(data.get("action", "reply")).lower()
            if action not in {"reply", "wait", "complete"}:
                action = "reply"
            return PlannerResult(
                action=action,
                reason=str(data.get("reason", "")),
                wait_ms=int(data["waitMs"]) if data.get("waitMs") else None,
            )
        except Exception as e:
            logger.warning(f"[ActionPlanner] plan failed: {e}")
            return PlannerResult(action="reply", reason="planner failed, default reply")