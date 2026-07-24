from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from zhenxun.services.ai.core.messages import ChatResponse, LLMMessage
from zhenxun.services.ai.llm import generate as ai_generate
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.log import logger


OnTextDelta = Callable[[str], Awaitable[None]]


class LLMCaller:
    async def chat(
        self,
        model_name: str,
        messages: list[LLMMessage],
        *,
        stream: bool = True,
        on_delta: OnTextDelta | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[Any] | None = None,
        timeout: float | None = None,
    ) -> ChatResponse:
        config = IntentBuilder()
        if temperature is not None:
            config = config.config_core(temperature=temperature)
        if max_tokens is not None:
            config = config.config_core(max_tokens=max_tokens)

        try:
            response = await ai_generate(
                messages=list(messages),
                model=model_name,
                config=config,
                timeout=timeout,
                extra={"tools": tools} if tools else None,
            )
        except Exception as e:
            logger.error(f"LLM 调用失败 model={model_name}: {e}", e=e)
            raise

        if stream and on_delta and response.text:
            text = strip_think_blocks(response.text)
            await on_delta(text)

        return response


def strip_think_blocks(text: str) -> str:
    import re

    if not text:
        return ""
    cleaned = re.sub(r"<think[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\|begin_of_thought\|>[\s\S]*?<\|end_of_thought\|>", "", cleaned)
    return cleaned.strip()