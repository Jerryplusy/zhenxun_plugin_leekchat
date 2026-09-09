from __future__ import annotations

from pathlib import Path
from typing import Any

from zhenxun.services.log import logger

from ...tts import GenerateByTextOptions, get_tts_service
from ...tts.runtime.language import detect_lang


async def synthesize_audio_base64(audio_config: Any, text: str) -> str | None:
    service = get_tts_service()
    if not service.is_ready():
        is_ready = await service.ready()
        if not is_ready:
            logger.debug("[leekchat.audio] TTS 服务未就绪，跳过语音合成")
            return None

    fallback_lang = "zh"
    try:
        fallback_lang = service._settings.defaultLang if service._settings else "zh"
    except Exception:
        fallback_lang = "zh"

    try:
        options = GenerateByTextOptions(
            text=text,
            textLang=detect_lang(text, fallback_lang),  # type: ignore[arg-type]
            mediaType="wav",
        )
        result = await service.generate_by_text(options)
    except Exception as exc:
        logger.warning(f"[leekchat.audio] TTS 合成失败: {exc}")
        return None

    file_path = result.filePath
    if not Path(file_path).is_file():
        logger.warning(f"[leekchat.audio] TTS 合成文件不存在: {file_path}")
        return None
    return file_path