from __future__ import annotations

from zhenxun.services.log import logger


class TopicTracker:
    """TODO: Topic 功能暂不实现"""

    def __init__(self, *_args, **_kwargs) -> None:
        logger.warning("TODO: TopicTracker 未实现 - Topic 功能")

    def get_topic_context(self, *_args, **_kwargs) -> str:
        return ""

    async def on_message(self, *_args, **_kwargs) -> None:
        return None