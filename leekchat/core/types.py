from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, runtime_checkable

class AIResponse(Protocol):
    text: str | None


class AIInstance(Protocol):
    async def generate(
        self, messages: Sequence[Any], model: str | None = ...
    ) -> AIResponse: ...


class AIService(Protocol):
    def getDefault(self) -> AIInstance | None: ...

class BotProtocol(Protocol):
    self_id: str
    async def call_api(self, api: str, **data: Any) -> Any: ...
    async def get_group_member_info(
        self, *, group_id: int, user_id: int, no_cache: bool = ...
    ) -> Any: ...
    async def get_group_member_list(self, *, group_id: int) -> Any: ...

@runtime_checkable
class ChatEvent(Protocol):
    self_id: int
    user_id: int
    message_type: str
OnTextContent = Callable[[str], Awaitable[None]]