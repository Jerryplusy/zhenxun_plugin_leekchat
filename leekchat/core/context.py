from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..configs import LeekchatConfig
    from ..humanize import HumanizeEngine
    from ..managers import (
        CooldownManager,
        GroupStructuredHistoryManager,
        IdleCheckManager,
        MessageQueueManager,
        QueueProcessor,
        RateLimitGuard,
        RateLimiter,
        SessionManager,
        SessionTurnScheduler,
        SkillSessionManager,
    )

    from .config_provider import ChatConfigProvider
    from .tools.context import ToolContext
    from .types import AIInstance, AIService


@dataclass
class ChatMessage:
    id: int | None = None
    session_id: str = ""
    role: str = "user"
    content: str = ""
    user_id: int | None = None
    user_name: str | None = None
    user_role: str | None = None
    user_title: str | None = None
    group_id: int | None = None
    group_name: str | None = None
    timestamp: int = 0
    message_id: int | None = None


@dataclass
class TargetMessage:
    user_name: str = ""
    user_id: int = 0
    user_role: str = "member"
    user_title: str | None = None
    content: str = ""
    message_id: int | None = None
    timestamp: int = 0


@dataclass
class ChatResult:
    messages: list[str] = field(default_factory=list)
    pending_at: list[int] = field(default_factory=list)
    pending_poke: list[int] = field(default_factory=list)
    pending_quote: int | None = None
    tool_calls: list[dict] = field(default_factory=list)
    emoji_path: str | None = None
    protocol_messages: list[object] = field(default_factory=list)


@dataclass
class PromptCtx:
    config: LeekchatConfig
    bot_nickname: str
    bot_role: str = "member"
    is_group: bool = True
    group_name: str | None = None
    member_count: int | None = None
    ai_service: AIService | None = None
    target_message: TargetMessage | None = None
    reply_context: dict | None = None
    prompt_injections: list[dict] | None = None
    active_skills_info: str | None = None
    planner_thoughts: str | None = None
    enable_external_skills: bool = False
    trigger_skill_role: str = "member"
    chat_history: list[ChatMessage] = field(default_factory=list)
    current_emotion: str | None = None
    expression_context: str | None = None
    memory_context: str | None = None
    topic_context: str | None = None
    review_messages: dict | None = None


@dataclass
class ChatPluginContext:
    config_provider: ChatConfigProvider
    get_config: Callable[[int | None], Awaitable[LeekchatConfig]]
    db: object
    ai_instance: AIInstance | None = None
    work_ai_instance: AIInstance | None = None
    vision_ai_instance: AIInstance | None = None
    get_ai_instance: Callable[..., AIInstance | None] | None = None
    ai_service: AIService | None = None
    humanize: HumanizeEngine | None = None

    session_manager: SessionManager | None = None
    skill_manager: SkillSessionManager | None = None
    rate_limiter: RateLimiter | None = None
    queue_manager: MessageQueueManager | None = None
    group_structured_history: GroupStructuredHistoryManager | None = None
    cooldown_manager: CooldownManager | None = None
    idle_check_manager: IdleCheckManager | None = None
    queue_processor: QueueProcessor | None = None
    session_turn_scheduler: SessionTurnScheduler | None = None
    run_with_rate_limit_guard: RateLimitGuard | None = None
    run_chat: Callable[..., Awaitable[ChatResult]] | None = None
    build_tool_context: Callable[..., ToolContext] | None = None
    send_message: Callable[..., Awaitable[None]] | None = None
    send_ai_response: Callable[..., Awaitable[None]] | None = None
    send_emoji: Callable[..., Awaitable[None]] | None = None
    save_bot_messages: Callable[..., Awaitable[None]] | None = None
    get_group_history_messages: Callable[..., Awaitable[list[ChatMessage]]] | None = None
    get_group_info_data: Callable[..., Awaitable[dict]] | None = None
    get_humanize_contexts: Callable[..., Awaitable[dict]] | None = None
    build_history_media_options: Callable[..., object] | None = None
    build_structured_user_input_from_target: Callable[..., dict] | None = None
    start_cooldown_timer: Callable[..., Awaitable[None]] | None = None
    record_group_message_for_learning: Callable[..., Awaitable[None]] | None = None