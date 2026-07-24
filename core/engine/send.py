from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

from zhenxun.services.log import logger
from zhenxun.utils.platform import PlatformUtils


async def _read_image_bytes(image: bytes | str | Path) -> bytes:
    if isinstance(image, bytes):
        return image
    if isinstance(image, (str, Path)):
        path = Path(image)
        return await asyncio.to_thread(path.read_bytes)
    raise TypeError(f"unsupported image source: {type(image)}")


def _normalize_image_source(image: bytes | str | Path) -> str:
    if isinstance(image, str) and image.startswith(("file://", "base64://", "data:", "http://", "https://")):
        return image
    if isinstance(image, Path) or (isinstance(image, str) and Path(image).is_file()):
        return f"file://{image}"
    return str(image)


def _file_to_base64_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def _send_image_with_fallback(
    bot: Any,
    target_id: int | None,
    group_id: int | None,
    image: bytes | str | Path,
    prefix_text: str = "",
) -> None:
    from zhenxun.utils.message import MessageUtils
    from nonebot_plugin_alconna import Image, Target, Text

    text_seg = Text(prefix_text) if prefix_text else None
    image_seg = Image(_normalize_image_source(image))

    segments = []
    if text_seg is not None:
        segments.append(text_seg)
    segments.append(image_seg)

    msg = MessageUtils.build_message(segments)
    target: Any
    if group_id is not None:
        target = Target("group", str(group_id))
    else:
        target = Target("private", str(target_id))

    try:
        await msg.send(target=target, bot=bot)
    except Exception as e:
        if isinstance(image, (str, Path)):
            data_url = _file_to_base64_data_url(Path(image))
            segments = [text_seg, Image(data_url)] if text_seg else [Image(data_url)]
            fallback_msg = MessageUtils.build_message(segments)
            await fallback_msg.send(target=target, bot=bot)
        else:
            raise


async def send_text_message(
    bot: Any,
    group_id: int | None,
    user_id: int,
    text: str,
) -> None:
    from zhenxun.utils.message import MessageUtils

    if group_id is not None:
        await PlatformUtils.send_message(
            bot=bot, user_id=None, group_id=str(group_id), message=text
        )
    else:
        await PlatformUtils.send_message(
            bot=bot, user_id=str(user_id), group_id=None, message=text
        )


async def send_ai_response(
    bot: Any,
    group_id: int,
    messages: list[str],
    sent_indices: set[int] | None = None,
) -> None:
    from zhenxun.utils.message import MessageUtils
    from nonebot_plugin_alconna import Target

    for i, msg_text in enumerate(messages):
        if sent_indices and i in sent_indices:
            continue
        if not msg_text or not msg_text.strip():
            continue
        target = Target("group", str(group_id))
        msg = MessageUtils.build_message(msg_text)
        try:
            await msg.send(target=target, bot=bot)
        except Exception as e:
            logger.error(f"[send_ai_response] send failed: {e}", e=e)


async def send_emoji(bot: Any, group_id: int, emoji_path: str | None) -> None:
    if not emoji_path:
        return
    path = Path(emoji_path)
    if not path.is_file():
        logger.warning(f"[send_emoji] file not found: {emoji_path}")
        return
    await _send_image_with_fallback(bot, None, group_id, path)