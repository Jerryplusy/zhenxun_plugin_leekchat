from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger


async def get_media_by_message_id(ctx: Any, message_id: int, event: Any = None) -> dict | None:
    """占位：根据 message_id 获取图片/视频的 URL。"""
    logger.info(f"[multimodal] get_media_by_message_id message_id={message_id}")
    return None