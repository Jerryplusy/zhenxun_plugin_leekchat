from __future__ import annotations

from zhenxun.services.log import logger


class ExpressionLearner:
    """TODO: Expression 功能暂不实现"""

    def __init__(self, *_args, **_kwargs) -> None:
        logger.warning("TODO: ExpressionLearner 未实现 - Expression 功能")

    async def on_message(self, *_args, **_kwargs) -> None:
        return None

    def get_expression_context_for_user(self, *_args, **_kwargs) -> str:
        return ""