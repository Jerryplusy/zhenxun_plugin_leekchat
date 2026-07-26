from __future__ import annotations

from nonebot import on_command, on_message, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, NoticeEvent

from zhenxun.services.log import logger
from zhenxun.utils.manager.priority_manager import PriorityLifecycle

from ._metadata import __plugin_meta__
from .core import read_config_from_zhenxun, resolve_role_instances
from .core.config_provider import ChatConfigProvider
from .core.context import ChatPluginContext
from .core.engine import (
    build_structured_user_input_from_target,
    build_tool_context,
    finalize_chat_turn,
    get_group_history_messages,
    get_group_info_data,
    get_humanize_contexts,
    process_chat,
    run_chat,
)
from .core.engine.send import send_ai_response, send_emoji, send_text_message
from .core.media import build_history_media_options
from .core.media.recognition import recognize_group_media_event
from .core.skills import (
    get_skill_registry,
    install_api_hooks,
    uninstall_api_hooks,
)
from .handlers import handle_message, handle_poke
from .handlers.skills_cmd import _skills_handler as _skills_cmd_handler  # noqa: F401  ensure registered
from .humanize import HumanizeEngine
from .managers import (
    ChatDatabaseCleanup,
    DEFAULT_CLEANUP_CONFIG,
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
from .runtime import ChatRuntime

_plugin_context: ChatPluginContext | None = None
_chat_runtime: ChatRuntime | None = None


@PriorityLifecycle.on_startup(priority=20)
async def _init_plugin() -> None:
    global _plugin_context, _chat_runtime

    logger.info("[leekchat] initializing...")

    config = read_config_from_zhenxun()
    base = config["base"]
    settings = config["settings"]
    personalization = config["personalization"]

    config_provider = ChatConfigProvider(
        base_config=base,
        settings_config=settings,
        personalization_config=personalization,
    )

    resolved = resolve_role_instances(
        main_model=config["main_model"],
        working_model=config["working_model"],
        multimodal_working_model=config["vision_model"],
    )
    if not resolved:
        logger.error(
            "[leekchat] 未配置 AI 模型，请在 zhenxun AI 设置中配置 Provider 并填写 MAIN_MODEL"
        )
        return

    main_model = resolved.main
    work_model = resolved.work
    vision_model = resolved.vision

    session_manager = SessionManager(max_size=config_provider().maxSessions)
    queue_manager = MessageQueueManager()
    rate_limiter = RateLimiter()
    rate_limiter.set_config_provider(config_provider)
    skill_manager = SkillSessionManager(
        max_loaded_per_session=getattr(config_provider(), "skillMaxLoadedPerSession", 5)
    )

    class _DBProxy:
        async def get_messages(self, session_id, limit):
            from nonebot import get_bot

            bot = None
            self_id = 0
            try:
                bot = get_bot()
                self_id = int(bot.self_id) if bot else 0
            except Exception:
                pass
            try:
                prefix, raw_id = session_id.split(":", 1)
                gid = int(raw_id) if prefix == "group" else None
                uid = int(raw_id) if prefix == "personal" else None
            except Exception:
                gid = None
                uid = None
            return await get_group_history_messages(
                bot=bot,
                group_id=gid,
                session_id=session_id,
                limit=limit,
                self_id=self_id,
                media_config=config_provider(),
                user_id=uid,
            )

        async def get_messages_by_user(self, user_id, session_id=None, limit=20):
            from .models import ChatMessage as M

            qs = M.filter(user_id=user_id)
            if session_id:
                qs = qs.filter(session_id=session_id)
            rows = await qs.order_by("-timestamp").limit(limit).all()
            return [
                {
                    "sessionId": r.session_id,
                    "role": r.role,
                    "content": r.content,
                    "userId": r.user_id,
                    "userName": r.user_name,
                    "userRole": r.user_role,
                    "groupId": r.group_id,
                    "timestamp": r.timestamp,
                    "messageId": r.message_id,
                }
                for r in rows
            ]

    db_proxy = _DBProxy()

    work_ai_service = type("WorkAI", (), {"getDefault": lambda self=None: None})()
    humanize = HumanizeEngine(work_ai_service, db_proxy, config_provider)
    await humanize.init()

    rate_limit_guard = RateLimitGuard(rate_limiter)

    session_turn_scheduler = SessionTurnScheduler()

    async def _get_config(group_id: int | None = None):
        return config_provider()

    plugin_ctx = ChatPluginContext(
        config_provider=config_provider,
        get_config=_get_config,
        db=db_proxy,
        ai_instance=None,
        work_ai_instance=None,
        vision_ai_instance=None,
        get_ai_instance=None,
        ai_service=None,
        humanize=humanize,
        session_manager=session_manager,
        skill_manager=skill_manager,
        rate_limiter=rate_limiter,
        queue_manager=queue_manager,
        group_structured_history=GroupStructuredHistoryManager(),
        cooldown_manager=CooldownManager.__new__(CooldownManager),
        idle_check_manager=IdleCheckManager.__new__(IdleCheckManager),
        queue_processor=QueueProcessor.__new__(QueueProcessor),
        session_turn_scheduler=session_turn_scheduler,
        run_with_rate_limit_guard=rate_limit_guard,
        run_chat=run_chat,
        build_tool_context=build_tool_context,
        send_message=send_text_message,
        send_ai_response=send_ai_response,
        send_emoji=send_emoji,
        save_bot_messages=None,
        get_group_history_messages=get_group_history_messages,
        get_group_info_data=get_group_info_data,
        get_humanize_contexts=get_humanize_contexts,
        build_history_media_options=build_history_media_options,
        build_structured_user_input_from_target=build_structured_user_input_from_target,
    )

    cooldown_manager = CooldownManager(plugin_ctx)
    idle_check_manager = IdleCheckManager(plugin_ctx)
    queue_processor = QueueProcessor(plugin_ctx)
    plugin_ctx.cooldown_manager = cooldown_manager
    plugin_ctx.idle_check_manager = idle_check_manager
    plugin_ctx.queue_processor = queue_processor

    rate_limiter.set_queue_length_getter(lambda gid: queue_manager.get_queue_length(f"group:{gid}"))
    rate_limiter.start()

    cleanup = ChatDatabaseCleanup(getattr(config_provider(), "retention", DEFAULT_CLEANUP_CONFIG))
    await cleanup.start()
    await idle_check_manager.start()

    _plugin_context = plugin_ctx
    _chat_runtime = ChatRuntime(plugin_ctx)

    logger.info(
        f"[leekchat] loaded (main={main_model}, work={work_model}, vision={vision_model})"
    )


@PriorityLifecycle.on_startup(priority=25)
async def _init_skills() -> None:
    """晚于 init_plugin(4) 与自身 _init_plugin(20)，此时 PluginInfo 表已就绪"""
    if _plugin_context is None:
        return
    if not getattr(_plugin_context.config_provider(), "enableExternalSkills", False):
        logger.info("[leekchat] 外部技能未启用，跳过技能扫描")
        return
    install_api_hooks()
    await get_skill_registry().scan()


@PriorityLifecycle.on_shutdown(priority=20)
async def _shutdown_plugin() -> None:
    global _plugin_context, _chat_runtime
    if _plugin_context is None:
        return
    uninstall_api_hooks()
    ctx = _plugin_context
    ctx.cooldown_manager.dispose()
    ctx.idle_check_manager.dispose()
    ctx.queue_processor.dispose()
    ctx.session_turn_scheduler.dispose()
    ctx.queue_manager.dispose()
    await ctx.rate_limiter.stop()
    ctx.skill_manager.cleanup()
    _plugin_context = None
    _chat_runtime = None
    logger.info("[leekchat] unloaded")


_message_handler = on_message(priority=99, block=False)
_poke_handler = on_notice(priority=10)


@_message_handler.handle()
async def _(bot: Bot, event: MessageEvent) -> None:
    if _plugin_context is None:
        return
    await handle_message(_plugin_context, event, bot)


@_poke_handler.handle()
async def _(bot: Bot, event: NoticeEvent) -> None:
    if _plugin_context is None:
        return
    await handle_poke(_plugin_context, event, bot)
    await recognize_group_media_event(_plugin_context, event, bot)


def get_chat_runtime() -> ChatRuntime | None:
    return _chat_runtime


__all__ = ["__plugin_meta__", "get_chat_runtime"]
