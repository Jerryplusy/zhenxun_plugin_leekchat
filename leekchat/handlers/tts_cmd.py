from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Optional

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.permission import SUPERUSER

from zhenxun.services.log import logger
from zhenxun.utils.platform import PlatformUtils

from ..tts import GenerateByTextOptions, get_tts_service
from ..tts.constants import DATA_DIR
from ..tts.runtime.language import detect_lang

_TTS_CMD = on_command(
    "tts", permission=SUPERUSER, priority=5, block=True, aliases={"/tts", "tts"}
)


def _normalize_event_text(text: str) -> str:
    text = (text or "").strip()
    for prefix in ("/tts", "tts"):
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
            break
    return text


def _parse_args(text: str) -> list[str]:
    return [arg for arg in text.split() if arg]


def _build_help() -> str:
    return (
        "GPT-SoVITS 本地 TTS 命令\n\n"
        "/tts dl            - 触发模型下载与服务启动（仅 SUPERUSER）\n"
        "/tts del           - 停止服务并删除模型数据（仅 SUPERUSER）\n"
        "/tts <文本>        - 调用本地 TTS 推理并发送语音\n"
        "/tts status        - 查看当前 TTS 服务状态\n"
        "/tts help          - 显示本帮助\n"
        "注意：默认未启用、未下载模型；首次使用请发送 /tts dl。\n"
    )


def _safe_remove_dir(target: Path) -> tuple[bool, str]:
    if not target.exists():
        return False, f"目录不存在: {target}"
    try:
        shutil.rmtree(target)
        return True, f"已删除: {target}"
    except OSError as exc:
        return False, f"删除失败: {exc}"


async def _notify_superuser(
    bot: Bot | None, message: str, user_id: Optional[str | int] = None
) -> None:
    try:
        await PlatformUtils.send_superuser(bot, message, str(user_id) if user_id else None)
    except Exception as exc:
        logger.warning(f"[tts] 通知超级用户失败: {exc}")


async def _start_bootstrap(bot: Bot, event: MessageEvent) -> None:
    cfg = _load_tts_settings()
    service = get_tts_service()
    if service is None:
        await _TTS_CMD.send("TTS 服务单例不可用")
        return
    service.configure(cfg)
    if service.is_bootstrapping():
        await _TTS_CMD.send("TTS 服务正在启动/下载中，请稍候...")
        return
    if service.is_ready():
        await _TTS_CMD.send("TTS 服务已就绪，无需重复启动")
        return

    listener = _make_progress_listener(bot, event)
    try:
        await service.start_bootstrap(listener=listener)
    except Exception as exc:
        await _TTS_CMD.send(f"启动 TTS 服务失败: {exc}")
        return

    await _TTS_CMD.send(
        "已开始 GPT-SoVITS 模型下载与服务启动；\n"
        "下载/启动完成后会自动通知超级用户。\n"
        "首次启动约需 5-15 分钟，请耐心等待。"
    )

    async def _wait_and_notify() -> None:
        try:
            await service.wait_until_ready()
        except Exception as exc:
            await _notify_superuser(
                bot, f"[tts] GPT-SoVITS 启动失败: {exc}", user_id=event.user_id
            )
            return
        if service.is_ready():
            status = service.get_status()
            await _notify_superuser(
                bot,
                "[tts] GPT-SoVITS 服务已就绪\n"
                f"模型: {status.model}\n设备: {status.device}\n"
                f"监听: {status.host}:{status.port}\n"
                "现在可以发送 /tts <文本> 合成语音",
                user_id=event.user_id,
            )
        else:
            err = (service.get_status() or None) and service.get_status().lastError  # type: ignore[union-attr]
            await _notify_superuser(
                bot,
                f"[tts] GPT-SoVITS 服务未能就绪: {err or '未知错误'}",
                user_id=event.user_id,
            )

    asyncio.create_task(_wait_and_notify())


def _make_progress_listener(bot: Bot, event: MessageEvent):
    from ..tts.types import BootstrapState

    async def listener(state: BootstrapState) -> None:
        try:
            msg = f"[tts:{state.phase}] {state.message}"
            await bot.send_private_msg(user_id=event.user_id, message=msg)
        except Exception as exc:
            logger.debug(f"[tts] bootstrap progress 通知失败: {exc}")

    return listener


async def _delete_models(bot: Bot, event: MessageEvent) -> None:
    service = get_tts_service()
    if service is not None:
        await service.dispose()
    from ..tts import reset_tts_service as _reset

    _reset()
    ok, msg = _safe_remove_dir(DATA_DIR)
    await _TTS_CMD.send(
        f"{msg}\nTTS 模型数据{'已删除' if ok else '删除失败/不存在'}。\n"
        "下次使用请发送 /tts dl 重新下载。"
    )


def reset_service_singleton() -> None:
    from ..tts import reset_tts_service as _reset

    _reset()


async def _send_status(_bot: Bot, _event: MessageEvent) -> None:
    service = get_tts_service()
    if service is None:
        await _TTS_CMD.send("TTS 服务未初始化，请发送 /tts dl 触发首次启动")
        return
    status = service.get_status()
    if status is None:
        await _TTS_CMD.send("TTS 服务未初始化，请发送 /tts dl 触发首次启动")
        return
    flags = []
    flags.append("ready" if status.ready else "not ready")
    flags.append("bootstrapping" if status.bootstrapping else "idle")
    extra = f"\n最后错误: {status.lastError}" if status.lastError else ""
    await _TTS_CMD.send(
        f"TTS 服务状态:\n"
        f"  - {' / '.join(flags)}\n"
        f"  - 模型: {status.model}\n"
        f"  - 设备: {status.device or 'auto (尚未探测)'}\n"
        f"  - 监听: {status.host}:{status.port}\n"
        f"  - PID: {status.pid or '-'}\n"
        f"  - 数据目录: {DATA_DIR}{extra}"
    )


async def _synthesize_and_send(bot: Bot, event: MessageEvent, text: str) -> None:
    service = get_tts_service()
    if service is None:
        await _TTS_CMD.send("TTS 服务未初始化，请发送 /tts dl 触发首次启动")
        return
    cfg = _load_tts_settings()
    if getattr(service, "_settings", None) is None:
        service.configure(cfg)
    if not service.is_ready():
        is_ready = await service.ready()
        if not is_ready:
            status = service.get_status()
            err = (status and status.lastError) or "未就绪"
            await _TTS_CMD.send(
                f"TTS 服务尚未就绪 ({err})；请先发送 /tts dl 完成首次启动。"
            )
            return

    try:
        options = GenerateByTextOptions(
            text=text,
            textLang=detect_lang(text, cfg["defaultLang"]),  # type: ignore[arg-type]
            mediaType="wav",
        )
        result = await service.generate_by_text(options)
    except Exception as exc:
        logger.error(f"[tts] 推理失败: {exc}")
        await _TTS_CMD.send(f"TTS 推理失败: {exc}")
        return

    await _send_voice(bot, event, result.filePath)


async def _send_voice(bot: Bot, event: MessageEvent, file_path: str) -> None:
    seg = MessageSegment.record(file=file_path)
    target_type = getattr(event, "message_type", None)
    if target_type == "private":
        await bot.send_private_msg(user_id=event.user_id, message=Message(seg))
    else:
        await bot.send_group_msg(group_id=event.group_id, message=Message(seg))


def _load_tts_settings() -> dict:
    from ..core.config_provider import _read_flat_all

    flat = _read_flat_all()
    tts_block: dict = {}
    for key, value in flat.items():
        if not key.startswith("SETTINGS_tts_"):
            continue
        camel = key[len("SETTINGS_tts_"):]
        tts_block[camel] = value
    return tts_block


@_TTS_CMD.handle()
async def _(bot: Bot, event: MessageEvent) -> None:
    raw = event.get_plaintext().strip()
    args = _parse_args(_normalize_event_text(raw))

    if not args or args[0].lower() == "help":
        await _TTS_CMD.finish(_build_help())
        return

    sub = args[0].lower()

    if sub == "status":
        await _send_status(bot, event)
        return

    if sub == "dl":
        await _start_bootstrap(bot, event)
        return

    if sub == "del":
        await _delete_models(bot, event)
        return

    text = raw
    for prefix in ("/tts", "tts"):
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
            break
    if not text.strip():
        await _TTS_CMD.finish(_build_help())
        return

    await _synthesize_and_send(bot, event, text.strip())