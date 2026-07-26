from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configs import LeekchatConfig
    from ...core.context import TargetMessage
    from ...core.types import AIService, BotProtocol, ChatEvent

from .permissions import ToolPermission


@dataclass
class ToolContext:
    session_id: str
    group_id: int | None
    user_id: int
    config: LeekchatConfig
    ai_service: AIService | None = None
    db: object | None = None
    event: ChatEvent | None = None
    bot: BotProtocol | None = None
    trigger_skill_role: str = "member"
    bot_role: str = "member"
    user_permission: ToolPermission = ToolPermission.MEMBER
    pending_image_urls: list[str] = field(default_factory=list)
    on_text_content: Callable[[str], Awaitable[None]] | None = None
    sent_message_indices: set[int] = field(default_factory=set)
    target_message: TargetMessage | None = None