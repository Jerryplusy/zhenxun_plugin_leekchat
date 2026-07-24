from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger
from zhenxun.utils.http_utils import AsyncHttpx


async def search_web_with_searxng(config: Any, args: dict) -> dict:
    base_url = (getattr(config, "baseUrl", "") or "").rstrip("/")
    if not base_url:
        return {"success": False, "error": "SearXNG baseUrl not configured"}

    query = args.get("query") or ""
    if not query and args.get("queries"):
        for q in args.get("queries") or []:
            if q and str(q).strip():
                query = str(q).strip()
                break
    if not query:
        return {"success": False, "error": "query is required"}

    timeout_ms = getattr(config, "timeoutMs", 8000)
    timeout_s = timeout_ms / 1000 if timeout_ms else 8

    default_limit = getattr(config, "defaultLimit", 5)
    max_limit = getattr(config, "maxLimit", 8)
    requested_limit = int(args.get("limit") or default_limit)
    limit = max(1, min(requested_limit, max_limit))

    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "language": "zh-CN",
    }
    if args.get("time_range"):
        params["time_range"] = args["time_range"]
    if args.get("categories"):
        params["categories"] = ",".join(args["categories"])
    if args.get("engines"):
        params["engines"] = ",".join(args["engines"])

    url = f"{base_url}/search"
    try:
        resp = await AsyncHttpx.get(
            url, params=params, timeout=timeout_s, follow_redirects=True
        )
        if resp.status_code != 200:
            logger.warning(f"[searxng] non-200 status: {resp.status_code}")
            return {
                "success": False,
                "error": f"upstream returned status {resp.status_code}",
            }
        data = resp.json()
    except Exception as e:
        logger.error(f"[searxng] request failed: {e}", e=e)
        return {"success": False, "error": f"search request failed: {e}"}

    results = data.get("results") or []
    formatted = []
    for item in results[:limit]:
        formatted.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "") or item.get("snippet", ""),
                "engine": item.get("engine", ""),
            }
        )

    return {
        "success": True,
        "query": query,
        "count": len(formatted),
        "results": formatted,
    }