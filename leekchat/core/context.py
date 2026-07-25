from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
    protocol_messages: list[Any] = field(default_factory=list)


@dataclass
class PromptCtx:
    config: Any
    bot_nickname: str
    bot_role: str = "member"
    is_group: bool = True
    group_name: str | None = None
    member_count: int | None = None
    ai_service: Any | None = None
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
    config_provider: Any
    get_config: Any
    db: Any
    ai_instance: Any | None = None
    work_ai_instance: Any | None = None
    vision_ai_instance: Any | None = None
    get_ai_instance: Any | None = None
    ai_service: Any | None = None
    humanize: Any | None = None

    session_manager: Any | None = None
    skill_manager: Any | None = None
    rate_limiter: Any | None = None
    queue_manager: Any | None = None
    group_structured_history: Any | None = None
    cooldown_manager: Any | None = None
    idle_check_manager: Any | None = None
    queue_processor: Any | None = None
    session_turn_scheduler: Any | None = None

    run_with_rate_limit_guard: Any | None = None
    run_chat: Any | None = None
    build_tool_context: Any | None = None
    send_message: Any | None = None
    send_ai_response: Any | None = None
    send_emoji: Any | None = None
    save_bot_messages: Any | None = None
    get_group_history_messages: Any | None = None
    get_group_info_data: Any | None = None
    get_humanize_contexts: Any | None = None
    build_history_media_options: Any | None = None
    build_structured_user_input_from_target: Any | None = None
    start_cooldown_timer: Any | None = None
    record_group_message_for_learning: Any | None = None