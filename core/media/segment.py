from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger


def get_segment_url(segment: Any) -> str | None:
    """从 message segment 中提取 URL。"""
    if not segment:
        return None
    seg_type = getattr(segment, "type", None)
    if seg_type == "image":
        url = getattr(segment, "data", None)
        if isinstance(url, dict):
            return url.get("url") or url.get("file")
        return getattr(segment, "url", None)
    if seg_type == "video":
        data = getattr(segment, "data", None)
        if isinstance(data, dict):
            return data.get("url") or data.get("file")
    return None


def get_card_data(segment: Any) -> dict | None:
    """从 xml/json/lightapp/ark 段提取 card 数据。"""
    seg_type = getattr(segment, "type", None)
    if seg_type not in {"xml", "json", "lightapp", "ark"}:
        return None
    data = getattr(segment, "data", None)
    if isinstance(data, dict):
        return data
    return {"raw": str(data)} if data else None


def get_forward_id(segment: Any) -> str | None:
    """从 forward 段提取 ID。"""
    if getattr(segment, "type", None) != "forward":
        return None
    data = getattr(segment, "data", None)
    if isinstance(data, dict):
        return data.get("id")
    return None


def is_media_analysis_blocked(config: Any, user_id: int) -> bool:
    blacklist = getattr(getattr(config, "mediaAnalysisBlacklistUsers", None), "__iter__", lambda: [])()
    try:
        return int(user_id) in set(blacklist or [])
    except Exception:
        return False


def build_history_media_options(*_args, **_kwargs) -> dict:
    """占位 - 构建历史媒体处理选项"""
    return {}


async def get_segment_source_candidates(segment: Any) -> list[str]:
    """从消息段提取媒体候选 URL"""
    url = get_segment_url(segment)
    return [url] if url else []


async def get_video_source_candidates_from_message(_bot, _message_id) -> list[str]:
    return []