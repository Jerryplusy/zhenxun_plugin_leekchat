from __future__ import annotations

from zhenxun.services.log import logger


async def synthesize_audio_base64(audio_config, text: str) -> str | None:
    """TODO: Audio 语音合成功能暂不实现"""
    logger.warning("TODO: synthesize_audio_base64 未实现 - 语音消息功能")
    return None