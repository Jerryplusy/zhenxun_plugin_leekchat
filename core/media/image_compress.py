from __future__ import annotations

import base64
import io
from typing import Any

from zhenxun.services.log import logger

IMAGE_MAX_BYTES = 1 * 1024 * 1024
COMPRESS_MAX_WIDTH = 1280
COMPRESS_JPEG_QUALITY = 80

FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://qq.com/",
}


async def prepare_image_url_for_model(url: str) -> str:
    if not url:
        return url
    if url.startswith("data:"):
        return url
    if not (url.startswith("http://") or url.startswith("https://")):
        return url

    size = await _probe_size(url)
    if size is not None and size <= IMAGE_MAX_BYTES:
        return url

    raw = await _download_bytes(url)
    if not raw:
        return url
    if len(raw) <= IMAGE_MAX_BYTES:
        return url

    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            if img.width > COMPRESS_MAX_WIDTH:
                ratio = COMPRESS_MAX_WIDTH / img.width
                img = img.resize(
                    (COMPRESS_MAX_WIDTH, int(img.height * ratio)),
                    Image.LANCZOS,
                )
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=COMPRESS_JPEG_QUALITY)
            compressed = buf.getvalue()
        b64 = base64.b64encode(compressed).decode("ascii")
        logger.info(
            f"[image-compress] compressed {len(raw)} -> {len(compressed)} bytes url={url[:80]}"
        )
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        logger.warning(f"[image-compress] compress failed, using original: {e}")
        return url


async def prepare_image_urls_for_model(urls: list[str]) -> list[str]:
    if not urls:
        return []
    return [await prepare_image_url_for_model(u) for u in urls]


async def _probe_size(url: str) -> int | None:
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers=FETCH_HEADERS,
        ) as client:
            r = await client.head(url)
            if r.status_code >= 400:
                r = await client.get(url)
            r.raise_for_status()
            n = int(r.headers.get("content-length") or 0)
            return n if n > 0 else None
    except Exception:
        return None


async def _download_bytes(url: str) -> bytes:
    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers=FETCH_HEADERS,
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content
    except Exception as e:
        logger.warning(f"[image-compress] download failed {url[:80]}: {e}")
        return b""