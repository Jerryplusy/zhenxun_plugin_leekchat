from __future__ import annotations

from typing import Any

from zhenxun.services.log import logger


async def describe_image(
    ai: Any,
    image_url: str,
    model_name: str | None,
    raw_message: str | None = None,
) -> dict:
    """异步调用多模态工作模型描述图片"""
    if ai is None:
        return {"success": False, "error": "AI instance not available"}
    try:
        from zhenxun.services.ai.core.messages import LLMMessage
        from zhenxun.services.ai.core.messages.parts import ImagePart, TextPart

        prompt = "请简要描述这张图片的内容，重点描述用户可能关心的关键信息。"
        msg = LLMMessage.user([TextPart(text=prompt), ImagePart(url=image_url)])
        resp = await ai.generate(messages=[msg], model=model_name)
        return {"success": True, "description": resp.text or ""}
    except Exception as e:
        logger.error(f"[image_analyzer] describe_image failed: {e}", e=e)
        return {"success": False, "error": str(e)}


async def process_image(ai, image_url: str, model_name: str | None, db, run_ai_request) -> None:
    """异步处理图片：调用工作模型生成描述并写库"""
    try:
        result = await run_ai_request(
            lambda: describe_image(ai, image_url, model_name)
        )
        if result.get("success"):
            from ..models import ImageCache

            await ImageCache.create(
                hash=image_url,
                url=image_url,
                type="image",
                description=result["description"],
                created_at=int(__import__("time").time() * 1000),
            )
    except Exception as e:
        logger.error(f"[image_analyzer] process_image failed: {e}", e=e)