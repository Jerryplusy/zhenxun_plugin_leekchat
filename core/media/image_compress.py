from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger


async def prepare_image_urls_for_model(urls: list[str]) -> list[str]:
    """简化版本：直接返回原 URL"""
    if not urls:
        return []
    return list(urls)