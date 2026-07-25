from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...core.context import ChatMessage

from .permissions import ToolPermission


@dataclass
class ToolContext:
    session_id: str
    group_id: int | None
    user_id: int
    config: Any
    ai_service: Any | None = None
    db: Any | None = None
    event: Any | None = None
    bot: Any | None = None
    trigger_skill_role: str = "member"
    bot_role: str = "member"
    user_permission: ToolPermission = ToolPermission.MEMBER
    pending_image_urls: list[str] = field(default_factory=list)
    on_text_content: Any | None = None
    sent_message_indices: set[int] = field(default_factory=set)
    target_message: Any | None = None