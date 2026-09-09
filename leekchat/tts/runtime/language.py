from __future__ import annotations

from typing import Iterable

RE_ZH = r"[\u4e00-\u9fff]"
RE_JA = r"[\u3040-\u30ff\u31f0-\u31ff]"
RE_KO = r"[\uac00-\ud7af]"
RE_EN = r"[A-Za-z]"


def _count(text: str, pattern: str) -> int:
    import re

    return len(re.findall(pattern, text))


def detect_lang(text: str, fallback: str = "zh") -> str:
    if not text:
        return fallback
    sample = text[:400]
    zh = _count(sample, RE_ZH)
    ja = _count(sample, RE_JA)
    ko = _count(sample, RE_KO)
    en = _count(sample, RE_EN)
    max_v = max(zh, ja, ko, en)
    if max_v == 0:
        return fallback
    if max_v == zh:
        return "zh"
    if max_v == ja:
        return "ja"
    if max_v == ko:
        return "ko"
    return "en"


def is_chinese(text: str) -> bool:
    import re

    return bool(re.search(RE_ZH, text))


def is_japanese(text: str) -> bool:
    import re

    return bool(re.search(RE_JA, text))


def is_korean(text: str) -> bool:
    import re

    return bool(re.search(RE_KO, text))


def is_english(text: str) -> bool:
    import re

    return bool(re.search(RE_EN, text))