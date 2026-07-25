from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

from zhenxun.services.log import logger
from zhenxun.utils.platform import PlatformUtils


async def _build_ai_message(
    text: str,
    default_reply_id: int | None = None,
):
    """将 AI 动作标记转换为真正的通用消息段。"""
    from nonebot_plugin_alconna import At, Image, Reply, Text

    from zhenxun.plugins.zhenxun_plugin_leekchat.core.engine.stream_parser import (
        parse_line_markers,
    )
    from zhenxun.plugins.zhenxun_plugin_leekchat.core.media.markdown_message import (
        extract_standalone_markdown_block,
    )
    from zhenxun.plugins.zhenxun_plugin_leekchat.core.media.markdown_screenshot import (
        render_markdown_to_image,
    )
    from zhenxun.utils.message import MessageUtils

    parsed = parse_line_markers(text)
    segments = []

    if parsed.reply_requested:
        quote_id = parsed.quote_id or default_reply_id
        if quote_id is not None:
            segments.append(Reply(id=str(quote_id)))

    segments.extend(
        At(flag="user", target=str(user_id)) for user_id in parsed.at_users
    )

    markdown = extract_standalone_markdown_block(parsed.clean_text)
    if markdown is not None:
        rendered = await render_markdown_to_image(markdown, theme="auto")
        if rendered is not None:
            segments.append(Image(raw=rendered))
        elif markdown:
            segments.append(Text(markdown))
    elif parsed.clean_text:
        segments.append(Text(parsed.clean_text))

    if not segments:
        return None
    return MessageUtils.build_message(segments)


async def _read_image_bytes(image: bytes | str | Path) -> bytes:
    if isinstance(image, bytes):
        return image
    if isinstance(image, str | Path):
        path = Path(image)
        return await asyncio.to_thread(path.read_bytes)
    raise TypeError(f"unsupported image source: {type(image)}")


def _normalize_image_source(image: bytes | str | Path) -> str:
    if isinstance(image, str) and image.startswith(
        ("file://", "base64://", "data:", "http://", "https://")
    ):
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
    from nonebot_plugin_alconna import Image, Target, Text

    from zhenxun.utils.message import MessageUtils

    text_seg = Text(prefix_text) if prefix_text else None
    image_seg = Image(_normalize_image_source(image))

    segments = []
    if text_seg is not None:
        segments.append(text_seg)
    segments.append(image_seg)

    msg = MessageUtils.build_message(segments)
    target: Any
    if group_id is not None:
        target = Target.group(str(group_id))
    else:
        target = Target.user(str(target_id))

    try:
        await msg.send(target=target, bot=bot)
    except Exception:
        if isinstance(image, str | Path):
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
    default_reply_id: int | None = None,
) -> None:
    for i, msg_text in enumerate(messages):
        if sent_indices and i in sent_indices:
            continue
        if not msg_text or not msg_text.strip():
            continue
        from zhenxun.plugins.zhenxun_plugin_leekchat.core.engine.stream_parser import (
            parse_line_markers,
        )

        parsed = parse_line_markers(msg_text)
        if parsed.poke_users:
            for user_id in parsed.poke_users:
                try:
                    await bot.call_api(
                        "send_poke",
                        group_id=int(group_id),
                        user_id=int(user_id),
                    )
                except Exception as e:
                    logger.warning(f"[send_ai_response] poke failed: {e}", e=e)

        from nonebot_plugin_alconna import Target

        target = Target.group(str(group_id))
        msg = await _build_ai_message(msg_text, default_reply_id)
        if msg is None:
            continue
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
