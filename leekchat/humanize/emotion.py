from __future__ import annotations

import json
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

    def _default_emotion(self, group_id: int | None = None) -> str:
        cfg = self._config_provider(group_id) if group_id is not None else self._config_provider()
        configured = self._normalize_emotion_name(
            getattr(getattr(cfg, "emotion", None), "defaultEmotion", "default")
        )
        available = self.get_available_emotions(group_id)
        return configured if configured in available else "default"

    def get_current(self, session_id: str, group_id: int | None = None) -> EmotionState:
        """同步获取当前情绪状态；若不存在则返回默认情绪的占位状态。"""
        existing = self._state.get(session_id)
        if existing:
            return existing
        state = EmotionState(current=self._default_emotion(group_id), updated_at=0)
        self._state[session_id] = state
        return state

    def get_available_emotions(self, group_id: int | None = None) -> list[str]:
        cfg = self._config_provider(group_id) if group_id is not None else self._config_provider()
        emotions = (
            getattr(getattr(cfg, "emotion", None), "emotions", {}) or {}
        )
        names = [
            self._normalize_emotion_name(name)
            for name in emotions.keys()
        ]
        names = [n for n in names if n]
        # 去重但保序
        seen: set[str] = set()
        unique: list[str] = []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        if "default" not in seen:
            unique.insert(0, "default")
        return unique

    def get_reference_examples(self, emotion: str, group_id: int | None = None) -> list[str]:
        cfg = self._config_provider(group_id) if group_id is not None else self._config_provider()
        normalized = self._normalize_emotion_name(emotion)
        emotions = getattr(getattr(cfg, "emotion", None), "emotions", {}) or {}
        examples = self._normalize_examples(emotions.get(normalized, {}).get("examples"))
        if examples:
            return examples
        return self._normalize_examples(
            emotions.get(self._default_emotion(group_id), {}).get("examples")
        )

    def get_emotion(self, session_id: str) -> str | None:
        st = self._state.get(session_id)
        return st.current if st else None

    def set_emotion(
        self, session_id: str, emotion: str, group_id: int | None = None
    ) -> EmotionState:
        resolved = self._resolve_emotion(emotion, group_id)
        state = EmotionState(current=resolved, updated_at=int(time.time() * 1000))
        self._state[session_id] = state
        return state

    def parse_emotion_intent(self, text: str) -> str | None:
        match = _EMOTION_RE.search(text or "")
        return self._normalize_emotion_name(match.group(1)) if match else None

    def clean_emotion_markers(self, text: str) -> str:
        return _EMOTION_TAG_RE.sub("", text or "").strip()

    async def refresh_if_needed(
        self,
        session_id: str,
        bot_nickname: str,
        chat_history: list,
        target_message,
        group_id: int | None = None,
        force: bool = False,
    ) -> EmotionState:
        cfg = self._config_provider(group_id) if group_id is not None else self._config_provider()
        current = self.get_current(session_id, group_id)
        interval_ms = int(
            getattr(getattr(cfg, "emotion", None), "updateIntervalMs", 60 * 60_000)
            or 60 * 60_000
        )
        should_refresh = (
            force
            or current.updated_at <= 0
            or int(time.time() * 1000) - current.updated_at >= interval_ms
        )
        if not should_refresh:
            return current

        try:
            next_emotion = await self._decide_emotion(
                bot_nickname, chat_history, target_message, group_id
            )
            return self.set_emotion(session_id, next_emotion, group_id)
        except Exception as e:
            logger.warning(f"[EmotionAgent] decide failed: {e}")
            if current.updated_at <= 0:
                return self.set_emotion(
                    session_id, self._default_emotion(group_id), group_id
                )
            return current

    async def _decide_emotion(
        self,
        bot_nickname: str,
        chat_history: list,
        target_message,
        group_id: int | None = None,
    ) -> str:
        cfg = self._config_provider(group_id) if group_id is not None else self._config_provider()
        available = self.get_available_emotions(group_id)
        if not self._work_ai or not available:
            return self._default_emotion(group_id)

        history_lines: list[str] = []
        for msg in chat_history[-30:]:
            role = getattr(msg, "role", None) or "user"
            if role == "assistant":
                name = bot_nickname
            else:
                name = getattr(msg, "user_name", None) or "User"
            ts = getattr(msg, "timestamp", None)
            prefix = ""
            if ts:
                try:
                    import datetime as _dt

                    dt = _dt.datetime.fromtimestamp(int(ts) / 1000)
                    prefix = (
                        f"[{dt.strftime('%m-%d %H:%M')}] "
                    )
                except Exception:
                    prefix = ""
            content = getattr(msg, "content", "") or ""
            history_lines.append(f"{prefix}{name}: {content}")
        history_text = "\n".join(history_lines) or "(No recent messages)"

        target_text = getattr(target_message, "content", "") if target_message else ""
        target_name = getattr(target_message, "user_name", "User") if target_message else "User"

        system_prompt = (
            "You are an emotion state selector for a chat bot.\n"
            "\n"
            "Task:\n"
            "- Read the recent chat context and the target user message.\n"
            f"- Choose exactly one current emotion state for {bot_nickname}.\n"
            f"- Only choose from the available emotion names: {', '.join(available)}.\n"
            "- Do not decide how the bot should reply.\n"
            "- Do not mention tools, actions, or response strategy.\n"
            "- Return JSON only.\n"
            "\n"
            "Response format:\n"
            '{"emotion":"one_available_emotion","reason":"brief context-only reason"}'
        )
        user_prompt = (
            f"Recent chat context:\n{history_text}\n\n"
            f"Target user message:\n{target_name}: {target_text}"
        )

        try:
            working_model = getattr(cfg, "workingModel", None) or ""
            resp = await ai_generate(
                messages=[
                    LLMMessage(role="system", content=[TextPart(text=system_prompt)]),
                    LLMMessage(role="user", content=[TextPart(text=user_prompt)]),
                ],
                model=working_model,
                config=IntentBuilder().config_core(temperature=0.2, max_tokens=160),
            )
            content = (getattr(resp, "text", "") or "").strip()
            parsed = self._extract_json_object(content)
            if parsed and isinstance(parsed, dict):
                return self._resolve_emotion(parsed.get("emotion"), group_id)
            # 兼容纯文本首词返回
            picked = content.split()[:1]
            if picked:
                return self._resolve_emotion(picked[0], group_id)
        except Exception as e:
            logger.warning(f"[EmotionAgent] decide failed: {e}")
        return self._default_emotion(group_id)

    def _resolve_emotion(self, emotion, group_id: int | None) -> str:
        normalized = self._normalize_emotion_name(emotion)
        available = self.get_available_emotions(group_id)
        if normalized in available:
            return normalized
        return self._default_emotion(group_id)

    @staticmethod
    def _normalize_emotion_name(emotion) -> str:
        return str(emotion or "").strip().lower()

    @staticmethod
    def _normalize_examples(examples) -> list[str]:
        if not examples:
            return []
        if not isinstance(examples, list):
            return []
        return [str(item).strip() for item in examples if str(item).strip()]

    @staticmethod
    def _extract_json_object(content: str):
        """从文本中提取第一个 JSON 对象。容错处理非标准输出。"""
        if not content:
            return None
        content = content.strip()
        try:
            return json.loads(content)
        except Exception:
            pass
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            snippet = content[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                return None
        return None
