from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from zhenxun.services.ai.core.messages import ChatRequest, ChatResponse, LLMMessage
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.ai.llm.engine.router import LLMOrchestrator
from zhenxun.services.log import logger
from zhenxun.utils.pydantic_compat import model_dump

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
        debug: bool = False,
    ) -> ChatResponse:
        config = IntentBuilder()
        if temperature is not None:
            config = config.config_core(temperature=temperature)
        if max_tokens is not None:
            config = config.config_core(max_tokens=max_tokens)

        if debug:
            request_debug = model_dump(config.build())
            request_debug.update(
                {
                    "model": model_name,
                    "timeout": timeout,
                    "tools": tools,
                    "messages": [model_dump(message) for message in messages],
                }
            )
            logger.info(f"[leekchat][debug][main] LLM 请求: {request_debug}")

        try:
            resolved_config = config.build()
            request = ChatRequest(
                messages=list(messages),
                config=resolved_config,
                timeout=timeout,
                tools=tools,
            )
            response = await LLMOrchestrator.invoke(
                request,
                model_name=model_name,
                task="chat",
                override_config=resolved_config,
            )
        except Exception as e:
            logger.error(f"LLM 调用失败 model={model_name}: {e}", e=e)
            raise

        if debug:
            logger.info(f"[leekchat][debug][main] LLM 回复: {model_dump(response)}")

        # Tool-call responses can contain a short preamble. Do not stream it
        # before the tool loop has produced the actual final answer.
        if stream and on_delta and response.text and not response.tool_calls:
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
