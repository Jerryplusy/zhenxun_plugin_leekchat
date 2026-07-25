from __future__ import annotations

import base64
import io
from typing import Any

from zhenxun.services.log import logger


def _looks_like_gif(url: str, content_type: str | None = None) -> bool:
    if url and ".gif" in url.lower():
        return True
    if content_type and "image/gif" in content_type.lower():
        return True
    return False


async def is_gif_url(url: str, bot: Any | None = None) -> bool:
    if not url:
        return False
    if _looks_like_gif(url):
        return True
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://qq.com/",
            },
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if _looks_like_gif(url, ct):
                return True
            if r.content[:6] in (b"GIF87a", b"GIF89a"):
                return True
    except Exception as e:
        logger.debug(f"[gif_extractor] is_gif_url probe failed: {e}")
    return False


async def extract_gif_frames(
    gif_url: str,
    bot: Any | None = None,
    max_frames: int = 3,
) -> list[str] | None:
    if not gif_url:
        return None
    raw = await _download_bytes(gif_url, bot=bot)
    if not raw:
        return None
    if raw[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    try:
        from PIL import Image
    except ImportError:
        logger.warning("[gif_extractor] Pillow 未安装，跳过抽帧")
        return None
    try:
        with Image.open(io.BytesIO(raw)) as img:
            total = getattr(img, "n_frames", 1) or 1
            if total < 1:
                return None

            targets: list[int] = [0]
            if total > 1:
                mid = total // 2
                if mid not in targets:
                    targets.append(mid)
                if total - 1 not in targets:
                    targets.append(total - 1)
            targets = targets[:max_frames]

            frames: list[str] = []
            for idx in targets:
                img.seek(idx)
                frame = img.convert("RGBA")
                buf = io.BytesIO()
                frame.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                frames.append(f"data:image/png;base64,{b64}")

        logger.info(
            f"[gif_extractor] extracted {len(frames)} frames from {total}-frame GIF url={gif_url[:80]}"
        )
        return frames
    except Exception as e:
        logger.warning(f"[gif_extractor] extract failed: {e}")
        return None


async def _download_bytes(url: str, bot: Any | None = None) -> bytes:
    if bot is not None:
        try:
            resp = await bot.call_api("get_image", file=url)
            if isinstance(resp, (bytes, bytearray)):
                return bytes(resp)
            if isinstance(resp, str):
                data = resp
                if data.startswith("base64://"):
                    data = data[len("base64://"):]
                try:
                    return base64.b64decode(data)
                except Exception:
                    return b""
        except Exception as e:
            logger.debug(f"[gif_extractor] bot.get_image 失败，回退 httpx: {e}")
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content
    except Exception as e:
        logger.warning(f"[gif_extractor] download failed {url[:80]}: {e}")
        return b""