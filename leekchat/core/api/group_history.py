"""通过 OneBot V11 API 拉取群历史消息"""

from __future__ import annotations

import json
from typing import Any

from zhenxun.services.log import logger

from ..context import ChatMessage

_PER_CALL_LIMIT = 20
_HARD_CAP = 500


def _render_segments(
    segments: list,
    fallback: str = "",
    image_lookup: dict[str, str] | None = None,
    video_lookup: dict[str, str] | None = None,
    forward_lookup: dict[str, str] | None = None,
    card_lookup: dict[str, str] | None = None,
) -> str:
    image_lookup = image_lookup or {}
    video_lookup = video_lookup or {}
    forward_lookup = forward_lookup or {}
    card_lookup = card_lookup or {}
    tokens: list[tuple[str, str]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type")
        data = seg.get("data") or {}
        if seg_type == "text":
            tokens.append(("text", data.get("text", "")))
        elif seg_type == "at":
            tokens.append(("at", f"@{data.get('qq', '')}"))
        elif seg_type == "image":
            url = data.get("url") or data.get("file") or ""
            desc = image_lookup.get(url)
            label = f"[图片:{desc}]" if desc else "[图片]"
            tokens.append(("media", label))
        elif seg_type == "face":
            tokens.append(("media", f"[表情:{data.get('id', '')}]"))
        elif seg_type == "reply":
            tokens.append(("media", f"[回复 #{data.get('id', '')}]"))
        elif seg_type == "record":
            tokens.append(("media", "[语音]"))
        elif seg_type == "video":
            url = data.get("url") or data.get("file") or ""
            desc = video_lookup.get(url)
            label = f"[视频:{desc}]" if desc else "[视频]"
            tokens.append(("media", label))
        elif seg_type == "file":
            tokens.append(("media", f"[文件:{data.get('file', '')}]"))
        elif seg_type == "forward":
            fid = data.get("id") or ""
            desc = forward_lookup.get(fid)
            label = f"[合并转发:{desc}]" if desc else "[合并转发]"
            tokens.append(("media", label))
        elif seg_type in ("json", "cardimage", "xml"):
            key = json.dumps(data, ensure_ascii=False, sort_keys=True) if isinstance(data, dict) else str(data)
            desc = card_lookup.get(key)
            label = f"[卡片:{desc}]" if desc else "[卡片]"
            tokens.append(("media", label))
        elif seg_type == "poke":
            tokens.append(("media", "[戳一戳]"))
        elif seg_type == "share":
            tokens.append(("media", "[分享]"))
        elif seg_type == "location":
            tokens.append(("media", "[位置]"))
        else:
            tokens.append(("media", f"[{seg_type or '未知'}]"))

    out: list[str] = []
    for i, (kind, text) in enumerate(tokens):
        if i:
            prev_kind = tokens[i - 1][0]
            prev_text = out[-1] if out else ""
            both_text = prev_kind == "text" and kind == "text"
            if not both_text:
                need_sep = (
                    not prev_text[-1:].isspace()
                    and not text[:1].isspace()
                    and text[:1] not in "，。！？、；：）」』】》"
                )
                if need_sep:
                    out.append(" ")
        out.append(text)
    joined = "".join(out).strip()
    return joined or fallback


def _to_chat_message(
    raw: dict,
    self_id: int,
    group_id: int,
    image_lookup: dict[str, str] | None = None,
    video_lookup: dict[str, str] | None = None,
    forward_lookup: dict[str, str] | None = None,
    card_lookup: dict[str, str] | None = None,
    media_analysis_allowed: bool = True,
) -> ChatMessage:
    sender = raw.get("sender") or {}
    user_id = int(sender.get("user_id") or 0)
    role = "assistant" if self_id and user_id == self_id else "user"
    user_name = (
        sender.get("card")
        or sender.get("nickname")
        or (str(user_id) if user_id else "unknown")
    )
    user_role = (sender.get("role") or "member").lower()
    timestamp_ms = int(raw.get("time", 0)) * 1000
    message_id = raw.get("message_id")
    message_id = int(message_id) if message_id else None
    segments = raw.get("message") or []
    content = _render_segments(
        segments,
        fallback=raw.get("raw_message", ""),
        image_lookup=image_lookup if media_analysis_allowed else {},
        video_lookup=video_lookup if media_analysis_allowed else {},
        forward_lookup=forward_lookup if media_analysis_allowed else {},
        card_lookup=card_lookup if media_analysis_allowed else {},
    )
    return ChatMessage(
        id=message_id,
        session_id=f"group:{group_id}",
        role=role,
        content=content,
        user_id=user_id,
        user_name=user_name,
        user_role=user_role,
        group_id=group_id,
        timestamp=timestamp_ms,
        message_id=message_id,
    )


async def _build_image_lookup(urls: list[str]) -> dict[str, str]:
    """按 url 列表从 ImageCache 批量查描述"""
    from ...models import ImageCache

    if not urls:
        return {}
    urls = [u for u in urls if u]
    if not urls:
        return {}
    try:
        rows = await ImageCache.filter(url__in=urls).all()
    except Exception as e:
        logger.warning(f"[group_history] ImageCache 批量查询失败: {e}")
        return {}
    return {row.url: row.description for row in rows if row.url and row.description}


def _collect_image_urls(messages: list[dict]) -> list[str]:
    out: list[str] = []
    for m in messages:
        for seg in (m.get("message") or []):
            if isinstance(seg, dict) and seg.get("type") == "image":
                d = seg.get("data") or {}
                url = d.get("url") or d.get("file")
                if url and url not in out:
                    out.append(url)
    return out


def _collect_video_urls(messages: list[dict]) -> list[str]:
    out: list[str] = []
    for m in messages:
        for seg in (m.get("message") or []):
            if isinstance(seg, dict) and seg.get("type") == "video":
                d = seg.get("data") or {}
                url = d.get("url") or d.get("file") or d.get("path")
                if url and url not in out:
                    out.append(url)
    return out


def _collect_forward_ids(messages: list[dict]) -> list[str]:
    out: list[str] = []
    for m in messages:
        for seg in (m.get("message") or []):
            if isinstance(seg, dict) and seg.get("type") == "forward":
                fid = (seg.get("data") or {}).get("id")
                if fid and fid not in out:
                    out.append(fid)
    return out


def _collect_card_keys(messages: list[dict]) -> list[str]:
    import json as _json
    out: list[str] = []
    for m in messages:
        for seg in (m.get("message") or []):
            if isinstance(seg, dict) and seg.get("type") in ("json", "cardimage", "xml"):
                data = seg.get("data") or {}
                key = (
                    _json.dumps(data, ensure_ascii=False, sort_keys=True)
                    if isinstance(data, dict)
                    else str(data)
                )
                if key and key not in out:
                    out.append(key)
    return out


async def _build_video_lookup(urls: list[str]) -> dict[str, str]:
    from ..media.history_media import get_cached_video_tag_async
    if not urls:
        return {}
    out: dict[str, str] = {}
    for url in urls:
        try:
            tag = await get_cached_video_tag_async(url)
        except Exception as e:
            logger.warning(f"[group_history] 视频缓存查询失败 {url[:80]}: {e}")
            continue
        if tag.startswith("[video:") and tag.endswith("]"):
            out[url] = tag[len("[video:"):-1]
    return out


async def _build_forward_lookup(ids: list[str]) -> dict[str, str]:
    from ..media.history_media import get_cached_forward_tag_async
    if not ids:
        return {}
    out: dict[str, str] = {}
    for fid in ids:
        try:
            tag = await get_cached_forward_tag_async(fid)
        except Exception as e:
            logger.warning(f"[group_history] 转发缓存查询失败 id={fid}: {e}")
            continue
        if tag.startswith("[forward:") and tag.endswith("]"):
            out[fid] = tag[len("[forward:"):-1]
    return out


async def _build_card_lookup(keys: list[str]) -> dict[str, str]:
    from ..media.history_media import get_cached_card_tag_async
    if not keys:
        return {}
    out: dict[str, str] = {}
    for key in keys:
        try:
            tag = await get_cached_card_tag_async(key)
        except Exception as e:
            logger.warning(f"[group_history] 卡片缓存查询失败: {e}")
            continue
        if tag.startswith("[card:") and tag.endswith("]"):
            out[key] = tag[len("[card:"):-1]
    return out


def _extract_messages(resp: Any) -> list[dict]:
    if not resp:
        return []
    if not isinstance(resp, dict):
        return []
    if isinstance(resp.get("messages"), list):
        return resp["messages"]
    data = resp.get("data")
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return data["messages"]
    return []


async def fetch_group_history_messages(
    bot: Any,
    group_id: int,
    self_id: int,
    limit: int,
    media_config: Any | None = None,
) -> list[ChatMessage]:
    if bot is None or not group_id:
        logger.info(f"[group_history] group={group_id} 无 bot 或无 group_id，跳过")
        return []
    target = max(1, min(limit, _HARD_CAP))
    collected: list[dict] = []
    cursor: str | int | None = None
    rounds = 0

    while len(collected) < target:
        batch_size = min(_PER_CALL_LIMIT, target - len(collected))
        params: dict[str, Any] = {
            "group_id": str(group_id),
            "count": batch_size,
            "reverseOrder": True,
        }
        if cursor is not None:
            params["message_seq"] = str(cursor)
        try:
            resp = await bot.call_api("get_group_msg_history", **params)
        except Exception as e:
            logger.warning(
                f"[group_history] get_group_msg_history 失败 group={group_id} round={rounds}: {e}"
            )
            break

        messages = _extract_messages(resp)
        rounds += 1
        logger.info(
            f"[group_history] group={group_id} round={rounds} "
            f"requested={batch_size} got={len(messages)} total={len(collected)}/{target} "
            f"params={params}"
        )
        if not messages:
            if cursor is None and rounds == 1:
                fallback_params = {"group_id": str(group_id), "count": batch_size}
                try:
                    resp2 = await bot.call_api("get_group_msg_history", **fallback_params)
                    messages2 = _extract_messages(resp2)
                    logger.info(
                        f"[group_history] group={group_id} 兜底正序 got={len(messages2)} params={fallback_params}"
                    )
                    if messages2:
                        messages = messages2
                except Exception as e:
                    logger.warning(
                        f"[group_history] 兜底调用失败 group={group_id}: {e}"
                    )
            if not messages:
                try:
                    snippet = str(resp)[:300] if resp else "None"
                except Exception:
                    snippet = "<unprintable>"
                logger.info(
                    f"[group_history] group={group_id} 退出循环 raw_response_snippet={snippet}"
                )
                break

        collected.extend(messages)

        last = messages[-1]
        next_cursor = last.get("message_seq") or last.get("message_id")
        if not next_cursor or next_cursor == cursor:
            break
        if len(collected) >= target or len(messages) < batch_size:
            break
        cursor = next_cursor

    collected.sort(key=lambda m: int(m.get("time") or 0))
    collected = collected[:target]

    media_analysis_enabled = (
        True
        if media_config is None
        else bool(getattr(media_config, "enableMediaRecognition", True))
    )
    if media_analysis_enabled:
        image_lookup = await _build_image_lookup(_collect_image_urls(collected))
        video_lookup = await _build_video_lookup(_collect_video_urls(collected))
        forward_lookup = await _build_forward_lookup(_collect_forward_ids(collected))
        card_lookup = await _build_card_lookup(_collect_card_keys(collected))
    else:
        image_lookup = {}
        video_lookup = {}
        forward_lookup = {}
        card_lookup = {}
    blacklist = getattr(media_config, "mediaAnalysisBlacklistUsers", None) or []
    try:
        blocked_users = {int(value) for value in blacklist if str(value).strip()}
    except (TypeError, ValueError):
        blocked_users = set()
    img_urls = _collect_image_urls(collected)
    vid_urls = _collect_video_urls(collected)
    fwd_ids = _collect_forward_ids(collected)
    card_keys = _collect_card_keys(collected)
    logger.info(
        f"[group_history] group={group_id} 最终 {len(collected)} 条 (limit={target} rounds={rounds}) "
        f"图片 {len(img_urls)} 张 命中 {len(image_lookup)} "
        f"视频 {len(vid_urls)} 个 命中 {len(video_lookup)} "
        f"转发 {len(fwd_ids)} 条 命中 {len(forward_lookup)} "
        f"卡片 {len(card_keys)} 个 命中 {len(card_lookup)}"
    )
    return [
        _to_chat_message(
            m, self_id, group_id,
            image_lookup=image_lookup,
            video_lookup=video_lookup,
            forward_lookup=forward_lookup,
            card_lookup=card_lookup,
            media_analysis_allowed=(
                media_analysis_enabled
                and int((m.get("sender") or {}).get("user_id") or 0)
                not in blocked_users
            ),
        )
        for m in collected
    ]
