from __future__ import annotations

import asyncio
import base64
import hashlib
import time
from typing import Any

from zhenxun.services.log import logger


def content_hash(image_bytes: bytes) -> str:
    """图片**内容** SHA-256"""
    return hashlib.sha256(image_bytes or b"").hexdigest()


async def _download_image_bytes(
    image_url: str, bot: Any | None = None
) -> bytes:
    if not image_url:
        return b""
    if bot is not None:
        try:
            resp = await bot.call_api("get_image", file=image_url)
            if isinstance(resp, (bytes, bytearray)):
                return bytes(resp)
            if isinstance(resp, str):
                data = resp
                if data.startswith("base64://"):
                    data = data[len("base64://"):]
                try:
                    return base64.b64decode(data)
                except Exception:
                    return data.encode("utf-8", errors="ignore")
            if isinstance(resp, dict):
                for key in ("file", "data", "content", "base64"):
                    val = resp.get(key)
                    if isinstance(val, str):
                        d = val
                        if d.startswith("base64://"):
                            d = d[len("base64://"):]
                        try:
                            return base64.b64decode(d)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"[image_analyzer] bot.get_image 失败，回退 httpx: {e}")

    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            },
        ) as client:
            r = await client.get(image_url)
            r.raise_for_status()
            return r.content
    except Exception as e:
        logger.warning(f"[image_analyzer] 下载图片失败 {image_url[:80]}: {e}")
        return b""


async def describe_image(
    ai: Any,
    image_url: str,
    model_name: str | None,
    raw_message: str | None = None,
    rate_limit_guard: Any | None = None,
    rate_limit_context: dict | None = None,
    bot: Any | None = None,
) -> dict:
    try:
        from zhenxun.services.ai.core.messages import LLMMessage
        from zhenxun.services.ai.core.messages.parts import ImagePart, TextPart
        from zhenxun.services.ai.llm import generate as ai_generate

        if not model_name:
            return {"success": False, "error": "视觉模型未配置"}

        from .gif_extractor import is_gif_url, extract_gif_frames
        from .image_compress import prepare_image_url_for_model

        frames: list[str] | None = None
        if await is_gif_url(image_url, bot=bot):
            frames = await extract_gif_frames(image_url, bot=bot, max_frames=3)
            if frames:
                logger.info(
                    f"[image_analyzer] 识别为 GIF，已抽 {len(frames)} 帧 url={image_url[:80]}"
                )

        if frames:
            prepared = [await prepare_image_url_for_model(f) for f in frames]
            user_text = (
                f"Describe these {len(prepared)} frames from one animated image."
            )
            content: list = [TextPart(text=user_text)]
            for f in prepared:
                content.append(ImagePart(url=f))
            msg = LLMMessage.user(content)
        else:
            prepared_url = await prepare_image_url_for_model(image_url)
            msg = LLMMessage.user([TextPart(text="Describe this image."), ImagePart(url=prepared_url)])

        system_prompt = (
            "You are an image description assistant. Describe the image accurately "
            "for use in chat history.\n\n"
            "Instructions:\n"
            "- Return a concise factual description in Chinese, no more than 30 words.\n"
            "- Include important visible subjects, actions, expressions, and text.\n"
            "- Treat every input as a regular image. Do not classify it as a meme or sticker.\n"
            + (
                "- You are viewing frames from an animated image. Describe the overall action across the frames.\n"
                if frames else ""
            )
            + "\nResponse format (JSON):\n"
            '{"description":"brief Chinese description"}'
        )

        async def _do_call():
            kwargs = {"messages": [system_prompt, msg], "model": model_name, "temperature": 0.3}
            if ai is not None:
                return await ai.generate(**kwargs)
            return await ai_generate(**kwargs)

        if rate_limit_guard is not None:
            resp = await rate_limit_guard.run(
                _do_call,
                context={**(rate_limit_context or {}), "label": "vision"},
            )
        else:
            resp = await _do_call()
        if resp is None:
            return {"success": False, "error": "限流拒绝"}
        if not getattr(resp, "text", None):
            return {"success": False, "error": "模型返空"}

        description = _parse_json_description(resp.text) or resp.text.strip()
        return {"success": True, "description": description}
    except Exception as e:
        logger.error(f"[image_analyzer] describe_image failed: {e}", e=e)
        return {"success": False, "error": str(e)}


def _parse_json_description(text: str) -> str | None:
    import json
    import re

    if not text:
        return None
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except Exception:
        return None
    desc = obj.get("description") if isinstance(obj, dict) else None
    if not isinstance(desc, str):
        return None
    cleaned = desc.strip()
    return cleaned or "未知"


async def process_image(
    ai, image_url: str, model_name: str | None, db, run_ai_request
) -> None:
    """异步处理图片：调用工作模型生成描述并写库"""
    try:
        result = await run_ai_request(
            lambda: describe_image(ai, image_url, model_name)
        )
        if result.get("success"):
            from ...models import ImageCache

            await ImageCache.create(
                hash=image_url,
                url=image_url,
                type="image",
                description=result["description"],
                created_at=int(__import__("time").time() * 1000),
            )
    except Exception as e:
        logger.error(f"[image_analyzer] process_image failed: {e}", e=e)


async def get_or_recognize_image(
    image_url: str,
    model_name: str | None,
    bot: Any | None = None,
    rate_limit_guard: Any | None = None,
    rate_limit_context: dict | None = None,
) -> dict:
    from ...models import ImageCache

    if not image_url:
        return {"hash": "", "description": "", "cached": False}

    try:
        by_url = await ImageCache.get_or_none(url=image_url)
    except Exception as e:
        logger.warning(f"[image_analyzer] ImageCache url 查询失败: {e}")
        by_url = None
    if by_url and by_url.description:
        logger.info(
            f"[image_analyzer] url 命中 hash={(by_url.hash or '')[:12]} url={image_url[:80]}"
        )
        return {"hash": by_url.hash or "", "description": by_url.description, "cached": True}

    image_bytes = await _download_image_bytes(image_url, bot=bot)
    if image_bytes:
        ch = content_hash(image_bytes)
        logger.info(
            f"[image_analyzer] 下载完成 size={len(image_bytes)} content_sha256={ch[:12]} url={image_url[:80]}"
        )
    else:
        ch = ""
        logger.warning(
            f"[image_analyzer] 下载失败，将直接调视觉识别 url={image_url[:80]}"
        )

    if ch:
        try:
            by_hash = await ImageCache.get_or_none(hash=ch)
        except Exception as e:
            logger.warning(f"[image_analyzer] ImageCache hash 查询失败: {e}")
            by_hash = None
        if by_hash and by_hash.description:
            logger.info(
                f"[image_analyzer] 内容哈希命中 content_sha256={ch[:12]} url={image_url[:80]}"
            )
            return {"hash": ch, "description": by_hash.description, "cached": True}

    if not model_name:
        logger.warning("[image_analyzer] 视觉模型未配置，跳过识别")
        return {"hash": ch, "description": "", "cached": False}

    logger.info(
        f"[image_analyzer] 开始视觉识别 content_sha256={(ch or '')[:12]} model={model_name} url={image_url[:80]}"
    )
    result = await describe_image(
        None, image_url, model_name,
        rate_limit_guard=rate_limit_guard,
        rate_limit_context=rate_limit_context,
        bot=bot,
    )
    if not result.get("success"):
        logger.error(
            f"[image_analyzer] 识别失败 content_sha256={(ch or '')[:12]}: {result.get('error')}"
        )
        return {"hash": ch, "description": "", "cached": False}

    description = result["description"]
    try:
        await ImageCache.create(
            hash=ch or image_url,
            url=image_url,
            type="image",
            description=description,
            created_at=int(time.time() * 1000),
        )
        logger.info(
            f"[image_analyzer] 识别完成并入库 content_sha256={(ch or '')[:12]} desc_len={len(description)}"
        )
    except Exception as e:
        logger.warning(
            f"[image_analyzer] 写库冲突（可能并发识别同 URL）: {e}"
        )
    return {"hash": ch, "description": description, "cached": False}


