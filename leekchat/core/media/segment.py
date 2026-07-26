from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configs import LeekchatConfig
    from ..types import BotProtocol


def _segment_data(segment: Any) -> tuple[str | None, dict[str, Any]]:
    if isinstance(segment, dict):
        segment_type = segment.get("type")
        data = segment.get("data") or {}
    else:
        segment_type = getattr(segment, "type", None)
        data = getattr(segment, "data", None) or {}
    return segment_type, data if isinstance(data, dict) else {}


def get_segment_type(segment: Any) -> str | None:
    return _segment_data(segment)[0]


def get_segment_url(segment: Any) -> str | None:
    segment_type, data = _segment_data(segment)
    if segment_type not in {"image", "video"}:
        return None
    for key in ("url", "file", "path"):
        value = data.get(key)
        if value:
            return str(value)
    return None


def get_segment_source_candidates(segment: Any) -> list[str]:
    """提取图片/视频消息段的全部 URL 候选。"""
    segment_type, data = _segment_data(segment)
    if segment_type not in {"image", "video"}:
        return []
    return list(dict.fromkeys(
        str(data[key]) for key in ("url", "file", "path") if data.get(key)
    ))


def get_forward_id(segment: Any) -> str:
    segment_type, data = _segment_data(segment)
    if segment_type != "forward":
        return ""
    value = segment.get("id") if isinstance(segment, dict) else getattr(segment, "id", None)
    return str(value or data.get("id") or "").strip()


def get_card_data(segment: Any) -> str:
    segment_type, data = _segment_data(segment)
    if segment_type not in {"json", "xml", "ark", "lightapp", "cardimage"}:
        return ""
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


async def get_video_source_candidates_from_message(
    bot: "BotProtocol | None", message_id: int | str | None
) -> list[str]:
    if bot is None or message_id is None:
        return []
    try:
        result = await bot.call_api("get_msg", message_id=message_id)
    except Exception:
        return []
    data = result or {}
    segments = data.get("message") or data.get("data", {}).get("message") or []
    if not isinstance(segments, list):
        return []
    urls: list[str] = []
    for segment in segments:
        if get_segment_type(segment) != "video":
            continue
        for url in get_segment_source_candidates(segment):
            if url not in urls:
                urls.append(url)
    return urls


def is_media_analysis_blocked(config: "LeekchatConfig", user_id: int) -> bool:
    blacklist = getattr(config, "mediaAnalysisBlacklistUsers", None) or []
    try:
        blocked_ids = {int(value) for value in blacklist if str(value).strip()}
        return int(user_id) in blocked_ids
    except (TypeError, ValueError):
        return False


def build_history_media_options(*_args, **_kwargs) -> dict:
    return {}
