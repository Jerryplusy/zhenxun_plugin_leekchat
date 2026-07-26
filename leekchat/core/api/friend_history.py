"""通过 OneBot V11 API 拉取好友历史消息"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zhenxun.services.log import logger

from ..context import ChatMessage

if TYPE_CHECKING:
    from ..types import BotProtocol

_PER_CALL_LIMIT = 20
_HARD_CAP = 500


def _render_segments(
    segments: list,
    fallback: str = "",
) -> str:
    tokens: list[str] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type")
        data = seg.get("data") or {}
        if seg_type == "text":
            tokens.append(data.get("text", ""))
        elif seg_type == "face":
            tokens.append(f"[表情:{data.get('id', '')}]")
        elif seg_type == "image":
            tokens.append("[图片]")
        elif seg_type == "reply":
            tokens.append(f"[回复 #{data.get('id', '')}]")
        elif seg_type == "record":
            tokens.append("[语音]")
        elif seg_type == "video":
            tokens.append("[视频]")
        elif seg_type == "file":
            tokens.append(f"[文件:{data.get('file', '')}]")
        elif seg_type == "forward":
            tokens.append("[合并转发]")
        elif seg_type in ("json", "cardimage", "xml"):
            tokens.append("[卡片]")
        elif seg_type == "poke":
            tokens.append("[戳一戳]")
        elif seg_type == "share":
            tokens.append("[分享]")
        elif seg_type == "location":
            tokens.append("[位置]")
        else:
            tokens.append(f"[{seg_type or '未知'}]")

    text = "".join(tokens).strip()
    return text or fallback


def _to_chat_message(
    raw: dict,
    self_id: int,
    user_id: int,
) -> ChatMessage:
    sender = raw.get("sender") or {}
    sender_user_id = int(sender.get("user_id") or 0)
    role = "assistant" if self_id and sender_user_id == self_id else "user"
    user_name = (
        sender.get("card")
        or sender.get("nickname")
        or (str(sender_user_id) if sender_user_id else "unknown")
    )
    timestamp_ms = int(raw.get("time", 0)) * 1000
    message_id = raw.get("message_id")
    message_id = int(message_id) if message_id else None
    segments = raw.get("message") or []
    content = _render_segments(
        segments,
        fallback=raw.get("raw_message", ""),
    )
    return ChatMessage(
        id=message_id,
        session_id=f"personal:{user_id}",
        role=role,
        content=content,
        user_id=sender_user_id,
        user_name=user_name,
        user_role="member",
        group_id=None,
        timestamp=timestamp_ms,
        message_id=message_id,
    )


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


async def fetch_friend_history_messages(
    bot: "BotProtocol",
    user_id: int,
    self_id: int,
    limit: int,
) -> list[ChatMessage]:
    if bot is None or not user_id:
        logger.info(f"[friend_history] user={user_id} 无 bot 或无 user_id，跳过")
        return []

    target = max(1, min(limit, _HARD_CAP))
    collected: list[dict] = []
    cursor: str | int | None = None
    rounds = 0

    while len(collected) < target:
        batch_size = min(_PER_CALL_LIMIT, target - len(collected))
        params: dict[str, Any] = {
            "user_id": str(user_id),
            "count": batch_size,
            "reverse_order": True,
        }
        if cursor is not None:
            params["message_seq"] = str(cursor)
        try:
            resp = await bot.call_api("get_friend_msg_history", **params)
        except Exception as e:
            logger.warning(
                f"[friend_history] get_friend_msg_history 失败 user={user_id} round={rounds}: {e}"
            )
            if cursor is None and rounds == 0:
                try:
                    fallback_params = {"user_id": str(user_id), "count": batch_size}
                    resp = await bot.call_api("get_friend_msg_history", **fallback_params)
                except Exception as e2:
                    logger.warning(
                        f"[friend_history] 兜底调用失败 user={user_id}: {e2}"
                    )
                    break
            else:
                break

        messages = _extract_messages(resp)
        rounds += 1
        logger.info(
            f"[friend_history] user={user_id} round={rounds} "
            f"requested={batch_size} got={len(messages)} total={len(collected)}/{target}"
        )
        if not messages:
            logger.info(
                f"[friend_history] user={user_id} 退出循环 resp={str(resp)[:300] if resp else 'None'}"
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

    logger.info(
        f"[friend_history] user={user_id} 最终 {len(collected)} 条 (limit={target} rounds={rounds})"
    )

    return [
        _to_chat_message(m, self_id, user_id)
        for m in collected
    ]
