from __future__ import annotations

import re
import time
from dataclasses import dataclass

from zhenxun.services.ai.core.messages import LLMMessage, TextPart
from zhenxun.services.ai.llm import generate as ai_generate
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.log import logger


_EMOTION_RE = re.compile(r"\[emotion:([^\]]+)\]", re.IGNORECASE)
_EMOTION_TAG_RE = re.compile(r"\[emotion:[^\]]+\]", re.IGNORECASE)


@dataclass
class EmotionState:
    current: str
    updated_at: int


class EmotionAgent:
    def __init__(self, work_ai, config_provider) -> None:
        self._work_ai = work_ai
        self._config_provider = config_provider
        self._state: dict[str, EmotionState] = {}

    def _default_emotion(self, group_id: int | None) -> str:
        cfg = self._config_provider(group_id)
        return getattr(getattr(cfg, "emotion", None), "defaultEmotion", "default") or "default"

    def get_emotion(self, session_id: str) -> str | None:
        st = self._state.get(session_id)
        return st.current if st else None

    def set_emotion(self, session_id: str, emotion: str) -> None:
        self._state[session_id] = EmotionState(current=emotion, updated_at=int(time.time() * 1000))

    def parse_emotion_intent(self, text: str) -> str | None:
        match = _EMOTION_RE.search(text or "")
        return match.group(1).strip() if match else None

    def clean_emotion_markers(self, text: str) -> str:
        return _EMOTION_TAG_RE.sub("", text or "").strip()

    async def refresh_if_needed(self, session_id: str, bot_nickname: str, chat_history: list, target_message) -> EmotionState:
        cfg = self._config_provider(None)
        interval_ms = getattr(getattr(cfg, "emotion", None), "updateIntervalMs", 60 * 60_000)
        now = int(time.time() * 1000)
        existing = self._state.get(session_id)
        if existing and now - existing.updated_at < interval_ms:
            return existing

        current = await self._decide_emotion(bot_nickname, chat_history, target_message)
        state = EmotionState(current=current, updated_at=now)
        self._state[session_id] = state
        return state

    async def _decide_emotion(self, bot_nickname: str, chat_history: list, target_message) -> str:
        cfg = self._config_provider(None)
        emotions = getattr(getattr(cfg, "emotion", None), "emotions", {}) or {}
        if not self._work_ai or not emotions:
            return self._default_emotion(None)

        history_lines = []
        for msg in chat_history[-10:]:
            role = msg.role
            name = msg.user_name if role != "assistant" else bot_nickname
            history_lines.append(f"{name}: {msg.content}")
        history_text = "\n".join(history_lines) or "(no recent history)"

        target_text = target_message.content if target_message else ""
        target_name = target_message.user_name if target_message else ""
        target_id = target_message.user_id if target_message else 0

        emotion_names = ", ".join(emotions.keys())
        prompt = (
            f"Based on the chat history and the latest message from {target_name}({target_id}), "
            f"pick the most fitting emotion for {bot_nickname} to use in the reply.\n"
            f"Available emotions: {emotion_names}.\n"
            f"Reply with ONLY the emotion name, nothing else.\n\n"
            f"--- HISTORY ---\n{history_text}\n--- TARGET ---\n{target_text}"
        )
        try:
            working_model = (
                getattr(cfg, "workingModel", None) or getattr(cfg, "model", "")
            )
            resp = await ai_generate(
                messages=[LLMMessage.user(prompt)],
                model=working_model,
                config=IntentBuilder().config_core(temperature=0.2, max_tokens=20),
            )
            picked = (resp.text or "").strip().split()[0:1]
            if picked:
                name = picked[0].lower()
                if name in emotions:
                    return name
        except Exception as e:
            logger.warning(f"[EmotionAgent] decide failed: {e}")
        return self._default_emotion(None)