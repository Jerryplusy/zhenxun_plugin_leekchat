from __future__ import annotations

import re
from typing import TYPE_CHECKING

from zhenxun.services.ai.core.messages import LLMMessage, TextPart
from zhenxun.services.ai.llm import generate as ai_generate
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.log import logger
from zhenxun.utils.http_utils import AsyncHttpx

if TYPE_CHECKING:
    from ...configs import WebReaderConfig
    from ..types import AIInstance

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_RE = re.compile(r"<script\b[^>]*>[\s\S]*?</script>", re.IGNORECASE)
_STYLE_RE = re.compile(r"<style\b[^>]*>[\s\S]*?</style>", re.IGNORECASE)


def _strip_html(html: str) -> str:
    html = _SCRIPT_RE.sub(" ", html)
    html = _STYLE_RE.sub(" ", html)
    text = _HTML_TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text)
    return text.strip()


async def _fetch_html(url: str, config: "WebReaderConfig") -> tuple[str | None, str | None]:
    timeout_s = getattr(config, "timeoutMs", 10000) / 1000
    max_bytes = getattr(config, "maxHtmlBytes", 1_500_000)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; leekchat/1.0)"}
    try:
        resp = await AsyncHttpx.get(
            url, headers=headers, timeout=timeout_s, follow_redirects=True
        )
        if resp.status_code != 200:
            return None, f"upstream returned status {resp.status_code}"
        content_type = resp.headers.get("content-type", "")
        allowed = getattr(config, "allowedContentTypes", []) or []
        if allowed and content_type:
            if not any(ct in content_type for ct in allowed):
                return None, f"unsupported content-type: {content_type}"
        body = resp.text
        if len(body.encode("utf-8")) > max_bytes:
            body = body[: max_bytes // 2]
        return body, None
    except Exception as e:
        logger.error(f"[web_reader] fetch failed: {e}", e=e)
        return None, f"fetch failed: {e}"


async def read_web_page(
    ai: "AIInstance | None",
    working_model: str,
    config: "WebReaderConfig",
    args: dict,
) -> dict:
    url = (args.get("url") or "").strip()
    if not url:
        return {"success": False, "error": "url is required"}
    if not url.startswith(("http://", "https://")):
        return {"success": False, "error": "url must be http(s)"}

    html, error = await _fetch_html(url, config)
    if error or not html:
        return {"success": False, "error": error or "no content"}

    text = _strip_html(html)
    max_chars = getattr(config, "maxExtractedChars", 12000)
    if len(text) > max_chars:
        text = text[:max_chars]

    if getattr(config, "useWorkingModel", True):
        question = (args.get("question") or "").strip()
        focus_block = f"\nFocus: {question}" if question else ""
        prompt = (
            "Compress the following webpage content into a concise, information-dense passage. "
            "Preserve key facts, names, dates, and quotes. Omit navigation, ads, and boilerplate.\n\n"
            f"---PAGE---\n{text}\n---END---{focus_block}"
        )
        try:
            if ai is not None:
                compressed = await ai.generate(
                    messages=[LLMMessage.user(prompt)],
                    model=working_model,
                )
            else:
                compressed = await ai_generate(
                    messages=[LLMMessage.user(prompt)],
                    model=working_model,
                    config=IntentBuilder().config_core(
                        temperature=0.2, max_tokens=1200
                    ),
                )
            output = compressed.text or text
        except Exception as e:
            logger.warning(f"[web_reader] worker compression failed: {e}")
            output = text
    else:
        output = text

    return {
        "success": True,
        "url": url,
        "content": output,
    }
