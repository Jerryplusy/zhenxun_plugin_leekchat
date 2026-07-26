from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import nonebot
from nonebot.adapters import Bot as BaseBot
from nonebot.exception import MockApiException
from nonebot.message import handle_event

from zhenxun.services.log import logger

if TYPE_CHECKING:
    from ..tools.context import ToolContext

_SEND_APIS = {
    "send_msg",
    "send_group_msg",
    "send_private_msg",
    "send_group_forward_msg",
    "send_private_forward_msg",
}
_FORWARD_APIS = {"send_group_forward_msg", "send_private_forward_msg"}


@dataclass
class CaptureState:
    mode: str = "send"
    group_id: int | None = None
    user_id: int | None = None
    active: bool = True
    captured: list[str] = field(default_factory=list)


_capture_ctx: ContextVar[CaptureState | None] = ContextVar(
    "leekchat_skill_capture", default=None
)


def _match(state: CaptureState, data: dict) -> bool:
    api_group = data.get("group_id")
    if state.group_id is not None:
        return api_group is not None and str(api_group) == str(state.group_id)
    if api_group is not None:
        return False
    api_user = data.get("user_id")
    return api_user is not None and str(api_user) == str(state.user_id)


def _segment_to_text(seg: Any) -> str:
    seg_type = getattr(seg, "type", None)
    seg_data = getattr(seg, "data", None)
    if seg_type is None and isinstance(seg, dict):
        seg_type = seg.get("type")
        seg_data = seg.get("data") or {}
    if seg_type == "text":
        return str((seg_data or {}).get("text", ""))
    if seg_type == "at":
        return f"@{(seg_data or {}).get('qq', '')}"
    return f"[{seg_type or 'unknown'}]"


def _extract_text(api: str, data: dict) -> str:
    if api in _FORWARD_APIS:
        return "[合并转发消息]"
    message = data.get("message")
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    try:
        return "".join(_segment_to_text(seg) for seg in message)
    except TypeError:
        return str(message)


async def _quiet_interceptor(bot: BaseBot, api: str, data: dict[str, Any]) -> None:
    state = _capture_ctx.get()
    if (
        state is not None
        and state.active
        and state.mode == "quiet"
        and api in _SEND_APIS
        and _match(state, data)
    ):
        state.captured.append(_extract_text(api, data))
        raise MockApiException(result={"message_id": 0})


async def _send_recorder(
    bot: BaseBot,
    exception: Exception | None,
    api: str,
    data: dict[str, Any],
    result: Any,
) -> None:
    state = _capture_ctx.get()
    if (
        state is not None
        and state.active
        and state.mode == "send"
        and exception is None
        and api in _SEND_APIS
        and _match(state, data)
    ):
        state.captured.append(_extract_text(api, data))


_hooks_installed = False


def install_api_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    BaseBot.on_calling_api(_quiet_interceptor)
    BaseBot.on_called_api(_send_recorder)
    _hooks_installed = True


def uninstall_api_hooks() -> None:
    global _hooks_installed
    BaseBot._calling_api_hook.discard(_quiet_interceptor)
    BaseBot._called_api_hook.discard(_send_recorder)
    _hooks_installed = False


def _build_fake_event(event, command: str):
    from nonebot.adapters.onebot.v11 import Message

    now = int(time.time())
    message = Message(command)
    fake = event.copy(
        update={
            "message": message,
            "original_message": Message(command),
            "raw_message": command,
            "message_id": -now,
            "time": now,
            "to_me": False,
        }
    )
    # 合成事件标记：chkdsk 恶意触发检测据此豁免，leekchat 自身据此防回环
    object.__setattr__(fake, "_ai_triggered", True)
    return fake


async def execute_plugin_command(
    tool_ctx: "ToolContext",
    command: str,
    mode: str = "send",
    timeout: float = 30.0,
) -> dict:
    """以触发用户身份构造伪消息事件注入 nonebot 事件流，执行插件命令
    经过 zhenxun 全套 auth hooks（插件开关/权限/CD/金币/Ban），AI 无法越权
    """
    event = getattr(tool_ctx, "event", None)
    if event is None or not hasattr(event, "message"):
        return {"success": False, "error": "当前上下文缺少可复用的消息事件，无法执行命令"}

    bot = getattr(tool_ctx, "bot", None)
    if bot is None:
        try:
            bot = nonebot.get_bot(str(getattr(event, "self_id", "")))
        except Exception:
            return {"success": False, "error": "Bot 实例不可用，无法执行命令"}

    fake_event = _build_fake_event(event, command)
    state = CaptureState(
        mode=mode,
        group_id=getattr(tool_ctx, "group_id", None),
        user_id=getattr(tool_ctx, "user_id", None),
    )
    token = _capture_ctx.set(state)
    timed_out = False
    try:
        # create_task 复制当前 context，CaptureState 对整个处理链
        # （含插件内部 create_task 的延续）可见
        task = asyncio.create_task(handle_event(bot, fake_event))
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout)
        except asyncio.TimeoutError:
            timed_out = True
            logger.warning(
                f"[leekchat.skills] 命令执行超时({timeout}s): {command!r}"
            )
        except Exception as e:
            logger.error(f"[leekchat.skills] 命令执行异常: {command!r}: {e}", e=e)
    finally:
        state.active = False
        _capture_ctx.reset(token)

    replies = [r for r in state.captured if r]
    result: dict[str, Any] = {
        "success": not timed_out,
        "executed": command,
        "mode": mode,
        "replies": replies,
    }
    if timed_out:
        result["note"] = "Timed out. Plugin may still be running in the background; captured replies are above."
    elif not replies:
        result["note"] = (
            "No visible reply. Likely causes: command did not match (check the usage doc), "
            "the triggering user was blocked by permission/CD, or the plugin executed silently."
        )
    elif mode == "quiet":
        result["note"] = "Reply was intercepted and NOT sent to chat. Summarize the relevant content for the user."
    else:
        result["note"] = "Reply was sent to chat. The user has already seen it; do not repeat."
    return result
