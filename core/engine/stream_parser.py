from __future__ import annotations

from dataclasses import dataclass, field
import re

from ...utils.text import sanitize_brackets

_AT_RE = re.compile(r"\[at:(\d+)\]")
_REPLY_RE = re.compile(r"\[reply(?::(-?\d+))?\]", re.IGNORECASE)
_POKE_RE = re.compile(r"\[poke:(\d+)\]")
_AUDIO_RE = re.compile(r"\[audio:([^\]]+)\]", re.IGNORECASE)
_EMOTION_RE = re.compile(r"\[emotion:([^\]]+)\]", re.IGNORECASE)
_EMOTION_SHORT_RE = re.compile(r"\[(?:emo|emotion)\]", re.IGNORECASE)
_STICKER_RE = re.compile(r"^\s*\[\]\s*$", re.MULTILINE)


@dataclass
class ParsedLine:
    clean_text: str
    at_users: list[int] = field(default_factory=list)
    poke_users: list[int] = field(default_factory=list)
    quote_id: int | None = None
    reply_requested: bool = False
    emotion_name: str | None = None
    audio_text: str | None = None


def parse_line_markers(text: str) -> ParsedLine:
    cleaned = text or ""

    at_users = [int(m) for m in _AT_RE.findall(cleaned)]
    poke_users = [int(m) for m in _POKE_RE.findall(cleaned)]

    reply_match = _REPLY_RE.search(cleaned)
    quote_id = (
        int(reply_match.group(1))
        if reply_match and reply_match.group(1)
        else None
    )

    audio_match = _AUDIO_RE.search(cleaned)
    audio_text = audio_match.group(1).strip() if audio_match else None
    emotion_match = _EMOTION_RE.search(cleaned)
    emotion_name = emotion_match.group(1).strip().lower() if emotion_match else None

    cleaned = _AT_RE.sub("", cleaned)
    cleaned = _REPLY_RE.sub("", cleaned)
    cleaned = _POKE_RE.sub("", cleaned)
    cleaned = _AUDIO_RE.sub("", cleaned)
    cleaned = _STICKER_RE.sub("", cleaned)
    cleaned = _EMOTION_RE.sub("", cleaned)
    cleaned = _EMOTION_SHORT_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    # 收尾：残余半成品括号由 sanitize_brackets 收敛
    cleaned = sanitize_brackets(cleaned)

    return ParsedLine(
        clean_text=cleaned,
        at_users=at_users,
        poke_users=poke_users,
        quote_id=quote_id,
        reply_requested=reply_match is not None,
        emotion_name=emotion_name,
        audio_text=audio_text,
    )
