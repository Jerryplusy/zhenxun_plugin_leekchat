from __future__ import annotations

from .emoji import EmojiAgent
from .emotion import EmotionAgent
from .expression import ExpressionLearner
from .memory import MemoryRetrieval
from .planner import ActionPlanner
from .topic import TopicTracker


class HumanizeEngine:
    def __init__(self, work_ai, db, config_provider) -> None:
        self.memory_retrieval = MemoryRetrieval(work_ai, config_provider, db)
        self.topic_tracker = TopicTracker(work_ai, config_provider, db)
        self.action_planner = ActionPlanner(work_ai, config_provider)
        self.emotion_agent = EmotionAgent(work_ai, config_provider)
        self.emoji_agent = EmojiAgent(work_ai, config_provider)
        self.expression_learner = ExpressionLearner(work_ai, config_provider, db)

    async def init(self) -> None:
        return None