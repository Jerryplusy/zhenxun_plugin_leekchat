from __future__ import annotations

import time
from typing import Any

from zhenxun.services.log import logger


VIDEO_FULL_UPLOAD_MAX_BYTES = 50 * 1024 * 1024


async def summarize_history_video(sources: list[str], options: dict | None = None) -> dict:
    """占位 - 视频摘要写入缓存。"""
    logger.info(f"[history_media] summarize_video sources={len(sources)}")
    return {"success": True, "summary": "[video placeholder]"}


async def summarize_history_forward(forward_id: str, options: dict | None = None) -> dict:
    logger.info(f"[history_media] summarize_forward id={forward_id}")
    return {"success": True, "summary": "[forward placeholder]"}


async def summarize_history_card(card_data: Any, options: dict | None = None) -> dict:
    logger.info(f"[history_media] summarize_card")
    return {"success": True, "summary": "[card placeholder]"}


async def summarize_group_notice(notice: Any, options: dict | None = None) -> dict:
    logger.info(f"[history_media] summarize_group_notice")
    return {"success": True, "summary": "[group_notice placeholder]"}


async def download_video_for_analysis(_sources: list[str], options: dict | None = None) -> Any:
    return type("VideoFile", (), {"path": "", "byteSize": 0, "cleanup": lambda: None})()


async def probe_video_mime_type(_path: str) -> str:
    return "video/mp4"


async def summarize_video_content(_path: str, _size: int, options: dict | None = None) -> str:
    return "[video summary placeholder]"