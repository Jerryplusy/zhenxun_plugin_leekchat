from __future__ import annotations

from zhenxun.services.log import logger


async def is_gif_url(url: str) -> bool:
    if not url:
        return False
    return ".gif" in url.lower()


async def extract_gif_frames(url: str) -> dict:
    logger.info(f"[gif_extractor] extract_gif_frames url={url}")
    return {"frames": []}