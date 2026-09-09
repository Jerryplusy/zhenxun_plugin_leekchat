from __future__ import annotations

from zhenxun.services.log import logger

_PREFIX = "[tts]"


def info(message: str) -> None:
    logger.info(f"{_PREFIX} {message}")


def warn(message: str) -> None:
    logger.warning(f"{_PREFIX} {message}")


def error(message: str) -> None:
    logger.error(f"{_PREFIX} {message}")


def debug(message: str) -> None:
    logger.debug(f"{_PREFIX} {message}")


tts_log = type("TtsLog", (), {})()
tts_log.info = info
tts_log.warn = warn
tts_log.error = error
tts_log.debug = debug