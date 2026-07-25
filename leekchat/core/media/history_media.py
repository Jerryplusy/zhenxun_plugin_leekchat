from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from zhenxun.services.log import logger

VIDEO_FRAME_COUNT = 5
VIDEO_FULL_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
VIDEO_FRAME_EXTRACTION_FALLBACK = "用户发送了一个视频，但未能提取画面内容"

_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://qq.com/",
}


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data or b"").hexdigest()


def _hash_source(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


async def _download_bytes(url: str, bot: Any | None = None) -> bytes:
    if bot is not None:
        try:
            resp = await bot.call_api("get_image", file=url)
            if isinstance(resp, (bytes, bytearray)):
                return bytes(resp)
            if isinstance(resp, str):
                import base64
                data = resp
                if data.startswith("base64://"):
                    data = data[len("base64://"):]
                try:
                    return base64.b64decode(data)
                except Exception:
                    return b""
        except Exception as e:
            logger.debug(f"[history-media] bot.get_image 失败，回退 httpx: {e}")
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers=_FETCH_HEADERS,
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content
    except Exception as e:
        logger.warning(f"[history-media] download failed {url[:80]}: {e}")
        return b""


async def _download_video(sources: list[str], bot: Any | None = None) -> tuple[bytes, str] | None:
    for source in sources:
        try:
            raw = await _download_bytes(source, bot=bot)
            if raw:
                return raw, source
        except Exception as e:
            logger.warning(f"[history-media] download {source[:80]} failed: {e}")
    return None


async def _probe_video_duration(path_or_url: str) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path_or_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        duration = float(stdout.decode().strip())
        return duration if duration > 0 else 1.0
    except Exception:
        return 1.0


def _build_frame_timestamps(duration: float, frame_count: int) -> list[float]:
    if frame_count <= 1:
        return [0.0]
    max_ts = max(0.0, duration - 0.2)
    return [min(max_ts, (max_ts * i) / (frame_count - 1)) for i in range(frame_count)]


async def _extract_video_frames(
    video_url: str,
    frame_count: int = VIDEO_FRAME_COUNT,
) -> list[str]:
    try:
        duration = await _probe_video_duration(video_url)
        timestamps = _build_frame_timestamps(duration, frame_count)
    except Exception as e:
        logger.warning(f"[history-media] ffprobe failed: {e}")
        timestamps = [0.0]

    frames: list[str] = []
    import base64

    for i, ts in enumerate(timestamps):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            out_path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner", "-loglevel", "error",
                "-ss", str(ts),
                "-i", video_url,
                "-frames:v", "1",
                "-q:v", "2",
                "-y", out_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.warning(
                    f"[history-media] ffmpeg frame {i} failed: {stderr.decode()[-200:]}"
                )
                continue
            raw = Path(out_path).read_bytes()
            frames.append(
                f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}"
            )
        except FileNotFoundError as e:
            logger.warning(f"[history-media] ffmpeg not installed: {e}")
            break
        except Exception as e:
            logger.warning(f"[history-media] frame {i} extract failed: {e}")
        finally:
            try:
                os.unlink(out_path)
            except OSError:
                pass

    return frames


async def _summarize_video_by_full(
    video_bytes: bytes,
    model_name: str,
    ai_generate,
) -> str:
    from zhenxun.services.ai.core.messages import TextPart, VideoPart
    from zhenxun.services.ai.core.messages.models import SystemMessage, UserMessage

    mime = _probe_mime(video_bytes)
    from zhenxun.services.ai.llm.builder import IntentBuilder
    config = IntentBuilder().config_core(temperature=0.3)
    resp = await ai_generate(
        messages=[
            SystemMessage(content=[TextPart(text=(
                "You summarize video content for a chat history. Describe only what "
                "the video actually shows, objectively and concisely. Do not invent "
                "information that is not present."
            ))]),
            UserMessage(content=[
                TextPart(text=(
                    "This is a video sent by someone in a chat. Summarize the video's content "
                    "in Chinese for later use as chat history context: describe the visible "
                    "people/objects/actions/scenes/on-screen text, and briefly explain what "
                    "the video is about. Stay factual and concise; state uncertainty honestly when unclear."
                )),
                VideoPart(raw=video_bytes, mime_type=mime),
            ]),
        ],
        model=model_name,
        config=config,
    )
    return _normalize_summary(getattr(resp, "text", None))


async def _summarize_video_by_frames(
    video_url: str,
    model_name: str,
    ai_generate,
) -> str:
    from zhenxun.services.ai.core.messages import TextPart, ImagePart
    from zhenxun.services.ai.core.messages.models import SystemMessage, UserMessage

    frames = await _extract_video_frames(video_url)
    if not frames:
        return VIDEO_FRAME_EXTRACTION_FALLBACK

    content: list = [
        TextPart(text=(
            f"These {len(frames)} frames were sampled evenly from a video sent in a chat. "
            "Summarize the video's likely content in Chinese for later use as chat history "
            "context: note the visible people/objects/actions/on-screen text, and infer "
            "what the video is about. Stay factual and concise; if the frames are "
            "ambiguous or insufficient, say so honestly."
        )),
    ] + [ImagePart(url=url) for url in frames]

    from zhenxun.services.ai.llm.builder import IntentBuilder
    config = IntentBuilder().config_core(temperature=0.3)
    resp = await ai_generate(
        messages=[
            SystemMessage(content=[TextPart(text=(
                "You summarize video content for a chat history from evenly sampled frames. "
                "Describe what the frames plausibly show, objectively and concisely. "
                "Do not invent information that is not present."
            ))]),
            UserMessage(content=content),
        ],
        model=model_name,
        config=config,
    )
    return _normalize_summary(getattr(resp, "text", None))


def _probe_mime(_video_bytes: bytes) -> str:
    return "video/mp4"


async def summarize_history_video(
    video_source: str | list[str],
    bot: Any | None = None,
    ai_generate: Any | None = None,
    model_name: str | None = None,
    rate_limit_guard: Any | None = None,
    rate_limit_context: dict | None = None,
) -> str:
    sources = [video_source] if isinstance(video_source, str) else list(video_source)
    sources = [s for s in (s.strip() for s in sources) if s]
    if not sources or ai_generate is None or not model_name:
        return "[video]"

    cached = await _get_cached_summary(sources)
    if cached:
        return f"[video:{cached}]"

    downloaded = await _download_video(sources, bot=bot)
    if not downloaded:
        return "[video]"
    video_bytes, used_source = downloaded
    content_hash = _hash_bytes(video_bytes)

    cached_by_hash = await _get_cached_summary_by_hash("video", content_hash)
    if cached_by_hash and cached_by_hash != VIDEO_FRAME_EXTRACTION_FALLBACK:
        await _save_sources("video", content_hash, [used_source])
        return f"[video:{cached_by_hash}]"

    summary = ""
    if len(video_bytes) <= VIDEO_FULL_UPLOAD_MAX_BYTES:
        try:
            async def _call_full():
                return await _summarize_video_by_full(
                    video_bytes, model_name, ai_generate
                )
            full = await _run_with_guard(_call_full, rate_limit_guard, rate_limit_context)
            summary = full or ""
        except Exception as e:
            logger.warning(f"[history-media] 整体上传失败，回退抽帧: {e}")

    if not summary:
        try:
            async def _call_frames():
                return await _summarize_video_by_frames(
                used_source, model_name, ai_generate
            )
            frames_summary = await _run_with_guard(_call_frames, rate_limit_guard, rate_limit_context)
            summary = frames_summary or ""
        except Exception as e:
            logger.warning(f"[history-media] 抽帧识别失败: {e}")

    summary = summary or VIDEO_FRAME_EXTRACTION_FALLBACK
    if summary and summary != VIDEO_FRAME_EXTRACTION_FALLBACK:
        await _save_summary("video", content_hash, used_source, summary)
    await _save_sources("video", content_hash, [used_source])
    return f"[video:{summary}]"


def get_cached_history_video_tag(video_source: str | list[str]) -> str:
    return "[video]"


async def get_cached_video_tag_async(video_source: str | list[str]) -> str:
    sources = [video_source] if isinstance(video_source, str) else list(video_source)
    sources = [s for s in (s.strip() for s in sources) if s]
    if not sources:
        return "[video]"
    cached = await _get_cached_summary(sources)
    return f"[video:{cached}]" if cached else "[video]"


def _normalize_summary(value: str | None) -> str:
    import re as _re
    text = _re.sub(r"\s+", " ", (value or "").strip())
    return text[:500]


def _normalize_source_key(source: str) -> str:
    return _hash_source(source) if len(source) > 128 else source


async def _get_cached_summary(sources: list[str]) -> str | None:
    from ...models import MediaSummary, MediaSummarySource
    try:
        for source in sources:
            row = await MediaSummarySource.get_or_none(source_key=_normalize_source_key(source))
            if row and row.summary and row.summary.summary:
                summary = row.summary.summary
                if summary == VIDEO_FRAME_EXTRACTION_FALLBACK:
                    continue
                return summary
    except Exception as e:
        logger.warning(f"[history-media] 缓存查询失败: {e}")
    return None


async def _get_cached_summary_by_hash(kind: str, content_hash: str) -> str | None:
    from ...models import MediaSummary
    try:
        row = await MediaSummary.get_or_none(key=f"{kind}:{content_hash}")
        if row and row.summary:
            return row.summary if row.summary != VIDEO_FRAME_EXTRACTION_FALLBACK else None
        return row.summary if row else None
    except Exception as e:
        logger.warning(f"[history-media] hash 缓存查询失败: {e}")
        return None


async def _save_summary(kind: str, content_hash: str, source: str, summary: str) -> None:
    from ...models import MediaSummary
    try:
        await MediaSummary.create(
            key=f"{kind}:{content_hash}",
            kind=kind,
            source=source,
            summary=summary,
            created_at=int(asyncio.get_event_loop().time() * 1000) if hasattr(asyncio, "get_event_loop") else 0,
        )
    except Exception as e:
        logger.warning(f"[history-media] save summary 失败: {e}")


async def _save_sources(kind: str, content_hash: str, sources: list[str]) -> None:
    from ...models import MediaSummary, MediaSummarySource
    try:
        summary_row = await MediaSummary.get_or_none(key=f"{kind}:{content_hash}")
        if not summary_row:
            return
        for source in sources:
            try:
                await MediaSummarySource.create(
                    source_key=_normalize_source_key(source),
                    summary=summary_row,
                    created_at=int(asyncio.get_event_loop().time() * 1000) if hasattr(asyncio, "get_event_loop") else 0,
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"[history-media] save sources 失败: {e}")


async def _run_with_guard(coro_fn, rate_limit_guard, rate_limit_context):
    if rate_limit_guard is None:
        return await coro_fn()
    return await rate_limit_guard(
        coro_fn,
        context={**(rate_limit_context or {}), "label": "vision-video"},
    )


async def _summarize_text_content(
    label: str,
    text: str,
    working_model: str,
    ai_generate: Any,
) -> str:
    """文本摘要：调工作模型"""
    truncated = text[:8000] if len(text) > 8000 else text
    user_text = (
        f"{label}原始内容：\n{truncated}\n\n请概括成一句适合放进聊天历史的中文摘要。"
    )
    from zhenxun.services.ai.llm.builder import IntentBuilder
    config = IntentBuilder().config_core(temperature=0.3)
    resp = await ai_generate(
        messages=[
            {
                "role": "system",
                "content": (
                    "You summarize non-plain chat content for recent chat history. "
                    "Output Chinese only, concise and factual. Keep key names, titles, "
                    "links, amounts, and actions if present."
                ),
            },
            {"role": "user", "content": user_text},
        ],
        model=working_model,
        config=config,
    )
    return _normalize_summary(getattr(resp, "text", None))


def _extract_forward_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    messages = result.get("messages") or result.get("data", {}).get("messages") or []
    if not isinstance(messages, list):
        return ""
    lines: list[str] = []
    for node in messages:
        if not isinstance(node, dict):
            continue
        sender = node.get("sender") or {}
        sender_name = (
            sender.get("card")
            or sender.get("nickname")
            or node.get("nickname")
            or "unknown"
        )
        seg_text = _extract_message_segments_text(node.get("message") or node.get("content"))
        if seg_text:
            lines.append(f"{sender_name}: {seg_text}")
    return "\n".join(lines)


def _extract_message_segments_text(message: Any) -> str:
    if isinstance(message, str):
        return message.strip()
    if not isinstance(message, list):
        return ""
    parts: list[str] = []
    for seg in message:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type")
        data = seg.get("data") or {}
        if seg_type == "text":
            parts.append(str(data.get("text") or seg.get("text") or "").strip())
        elif seg_type == "at":
            qq = data.get("qq") or ""
            parts.append(f"@{qq}")
        elif seg_type == "image":
            parts.append("[图片]")
        elif seg_type == "video":
            parts.append("[视频]")
        elif seg_type == "forward":
            parts.append("[合并转发]")
        elif seg_type in ("json", "xml", "ark"):
            parts.append(
                str(data.get("data") or data.get("xml") or seg.get("data") or "").strip()
            )
    return " ".join(p for p in parts if p)


def _extract_card_prompt(source: str) -> str | None:
    parsed = _try_parse_json(source)
    if not parsed:
        return None
    prompt = parsed.get("prompt") if isinstance(parsed, dict) else None
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    return None


def _try_parse_json(value: str) -> Any:
    import json
    try:
        return json.loads(value)
    except Exception:
        return None


async def _get_cached_forward_summary(forward_id: str) -> str | None:
    from ...models import MediaSummarySource
    try:
        row = await MediaSummarySource.get_or_none(source_key=f"forward:{forward_id}")
        if row and row.summary and row.summary.summary:
            return row.summary.summary
    except Exception as e:
        logger.warning(f"[history-media] 转发缓存查询失败: {e}")
    return None


async def _get_cached_card_summary(card_data: str) -> str | None:
    from ...models import MediaSummarySource
    source_key = f"card:{card_data[:64]}"
    try:
        row = await MediaSummarySource.get_or_none(source_key=source_key)
        if row and row.summary and row.summary.summary:
            return row.summary.summary
    except Exception as e:
        logger.warning(f"[history-media] 卡片缓存查询失败: {e}")
    return None


async def summarize_history_forward(
    forward_id: str,
    bot: Any | None = None,
    ai_generate: Any | None = None,
    working_model: str | None = None,
    rate_limit_guard: Any | None = None,
    rate_limit_context: dict | None = None,
) -> str:
    fid = (forward_id or "").strip()
    if not fid or bot is None or ai_generate is None or not working_model:
        return "[forward]"

    cached = await _get_cached_forward_summary(fid)
    if cached:
        return f"[forward:{cached}]"

    try:
        result = await bot.call_api("get_forward_msg", id=fid)
    except Exception as e:
        logger.warning(f"[history-media] get_forward_msg 失败 id={fid}: {e}")
        return "[forward]"

    text = _extract_forward_text(result)
    if not text:
        return "[forward]"
    content_hash = _hash_source(text)

    cached_by_hash = await _get_cached_summary_by_hash("forward", content_hash)
    if cached_by_hash:
        await _save_sources("forward", content_hash, [f"forward:{fid}"])
        return f"[forward:{cached_by_hash}]"

    async def _call():
        return await _summarize_text_content(
            "合并转发消息", text, working_model, ai_generate
        )
    summary = await _run_with_guard(_call, rate_limit_guard, rate_limit_context)
    summary = _normalize_summary(summary)
    if not summary:
        return "[forward]"
    await _save_summary("forward", content_hash, f"forward:{fid}", summary)
    await _save_sources("forward", content_hash, [f"forward:{fid}"])
    return f"[forward:{summary}]"


async def summarize_history_card(
    card_data: str,
    ai_generate: Any | None = None,
    working_model: str | None = None,
    rate_limit_guard: Any | None = None,
    rate_limit_context: dict | None = None,
) -> str:
    source = (card_data or "").strip()
    if not source or ai_generate is None or not working_model:
        return "[card]"

    cached = await _get_cached_card_summary(source)
    if cached:
        return f"[card:{cached}]"

    content_hash = _hash_source(source)
    cached_by_hash = await _get_cached_summary_by_hash("card", content_hash)
    if cached_by_hash:
        await _save_sources("card", content_hash, [f"card:{source[:64]}"])
        return f"[card:{cached_by_hash}]"

    prompt_text = _extract_card_prompt(source)
    if prompt_text and 0 < len(prompt_text) < 100:
        summary = prompt_text
    else:
        async def _call():
            return await _summarize_text_content(
                "XML/JSON 卡片消息", prompt_text or source, working_model, ai_generate
            )
        summary = _normalize_summary(await _run_with_guard(_call, rate_limit_guard, rate_limit_context))
    if not summary:
        return "[card]"
    await _save_summary("card", content_hash, f"card:{source[:64]}", summary)
    await _save_sources("card", content_hash, [f"card:{source[:64]}"])
    return f"[card:{summary}]"


def _notice_value(notice: Any, *keys: str) -> Any:
    for key in keys:
        if isinstance(notice, dict):
            value = notice.get(key)
        else:
            value = getattr(notice, key, None)
        if value not in (None, ""):
            return value
    return None


def _extract_notice_text(notice: Any) -> str:
    nested = _notice_value(notice, "notice", "data")
    candidates = [
        _notice_value(notice, "message", "text", "content", "title", "msg", "raw_message"),
        _notice_value(nested, "message", "text", "content", "title", "msg"),
    ]
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            text = _extract_message_segments_text(value)
            if text:
                return text
    return ""


def _extract_notice_sender(notice: Any) -> tuple[int, str]:
    sender = _notice_value(notice, "sender") or {}
    user_id = _notice_value(
        notice,
        "user_id",
        "sender_id",
        "operator_id",
        "poster_id",
        "publisher_id",
    )
    if user_id is None:
        user_id = _notice_value(sender, "user_id")
    name = _notice_value(
        sender,
        "card",
        "nickname",
    ) or _notice_value(notice, "sender_name", "nickname", "publisher_name")
    try:
        normalized_id = int(user_id or 0)
    except (TypeError, ValueError):
        normalized_id = 0
    return normalized_id, str(name or normalized_id or "unknown")


def _notice_timestamp(notice: Any) -> int:
    value = _notice_value(
        notice, "publish_time", "time", "created_at", "create_time"
    )
    try:
        timestamp = int(value or 0)
    except (TypeError, ValueError):
        timestamp = 0
    return timestamp * 1000 if timestamp < 10**12 else timestamp


async def summarize_group_notice(
    notice: Any,
    ai_generate: Any | None = None,
    working_model: str | None = None,
    rate_limit_guard: Any | None = None,
    rate_limit_context: dict | None = None,
) -> dict[str, Any] | None:
    """摘要群公告，返回可写入聊天历史的用户消息载荷。"""
    if ai_generate is None or not working_model:
        return None
    text = _extract_notice_text(notice)
    if not text:
        return None

    async def _call():
        return await _summarize_text_content("群公告", text, working_model, ai_generate)

    summary = _normalize_summary(
        await _run_with_guard(_call, rate_limit_guard, rate_limit_context)
    )
    if not summary:
        return None
    user_id, user_name = _extract_notice_sender(notice)
    return {
        "content": f"发布了一条群公告：[group_notice:{summary}]",
        "user_id": user_id,
        "user_name": user_name,
        "user_role": "member",
        "timestamp": _notice_timestamp(notice),
        "message_id": int(_notice_value(notice, "message_id") or 0),
    }


async def get_cached_forward_tag_async(forward_id: str) -> str:
    fid = (forward_id or "").strip()
    if not fid:
        return "[forward]"
    cached = await _get_cached_forward_summary(fid)
    return f"[forward:{cached}]" if cached else "[forward]"


async def get_cached_card_tag_async(card_data: str) -> str:
    source = (card_data or "").strip()
    if not source:
        return "[card]"
    cached = await _get_cached_card_summary(source)
    return f"[card:{cached}]" if cached else "[card]"


def get_cached_history_forward_tag(forward_id: str) -> str:
    return "[forward]"


def get_cached_history_card_tag(card_data: str) -> str:
    return "[card]"
