from __future__ import annotations

import time

from zhenxun.services.log import logger

from ..models import ChatMessage, ImageCache, MediaSummary, MediaSummarySource, TopicRecord


class ChatDatabaseCleanup:
    def __init__(self, retention_config) -> None:
        self._config = retention_config

    async def cleanup_once(self) -> dict[str, int]:
        if not getattr(self._config, "enabled", False):
            return {}
        now = int(time.time() * 1000)
        result: dict[str, int] = {}

        msg_retention = getattr(self._config, "messageRetentionMs", 0)
        if msg_retention > 0:
            deleted = await ChatMessage.filter(timestamp__lt=now - msg_retention).delete()
            result["messages"] = deleted

        topic_retention = getattr(self._config, "topicRetentionMs", 0)
        if topic_retention > 0:
            deleted = await TopicRecord.filter(created_at__lt=now - topic_retention).delete()
            result["topics"] = deleted

        media_retention = getattr(self._config, "mediaSummaryRetentionMs", 0)
        if media_retention > 0:
            src_deleted = await MediaSummarySource.filter(
                created_at__lt=now - media_retention
            ).delete()
            sm_deleted = await MediaSummary.filter(
                created_at__lt=now - media_retention
            ).delete()
            result["media_summaries"] = sm_deleted + src_deleted

        image_retention = getattr(self._config, "imageRetentionMs", 0)
        if image_retention > 0:
            deleted = await ImageCache.filter(created_at__lt=now - image_retention).delete()
            result["images"] = deleted

        return result

    async def start(self) -> None:
        interval_ms = getattr(self._config, "cleanupIntervalMs", 60 * 60 * 1000)
        self._interval_s = interval_ms / 1000
        import asyncio

        self._task = asyncio.create_task(self._run_loop())

    async def _run_loop(self) -> None:
        import asyncio

        try:
            while True:
                await asyncio.sleep(self._interval_s)
                result = await self.cleanup_once()
                logger.info(f"[leekchat] cleanup result: {result}")
        except asyncio.CancelledError:
            return

    async def stop(self) -> None:
        if hasattr(self, "_task") and self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass


DEFAULT_CLEANUP_CONFIG = type(
    "DefaultCleanupConfig",
    (),
    {
        "enabled": True,
        "messageRetentionMs": 30 * 24 * 60 * 60 * 1000,
        "topicRetentionMs": 90 * 24 * 60 * 60 * 1000,
        "mediaSummaryRetentionMs": 30 * 24 * 60 * 60 * 1000,
        "imageRetentionMs": 60 * 24 * 60 * 60 * 1000,
        "cleanupIntervalMs": 60 * 60 * 1000,
    },
)()