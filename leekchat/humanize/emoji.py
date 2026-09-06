from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zhenxun.services.ai.core.messages import LLMMessage, TextPart
from zhenxun.services.ai.llm import generate as ai_generate
from zhenxun.services.ai.llm.builder import IntentBuilder
from zhenxun.services.log import logger


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
MEME_ROOT = PLUGIN_ROOT / "resources" / "meme"
ALLOWED_SUFFIX = {".gif", ".png", ".jpg", ".jpeg", ".webp"}

_STICKER_INTENT_LINE_RE = re.compile(r"^\s*\[\]\s*$", re.MULTILINE)


@dataclass
class StickerResult:
    cleaned_text: str
    success: bool
    emoji_path: str | None = None


class EmojiAgent:
    def __init__(self, work_ai, config_provider) -> None:
        self._work_ai = work_ai
        self._config_provider = config_provider
        self._characters: list[str] | None = None
        self._files_by_character: dict[str, list[Path]] | None = None

    def _ensure_index(self) -> None:
        if self._characters is not None:
            return
        chars: list[str] = []
        files_map: dict[str, list[Path]] = {}
        if MEME_ROOT.is_dir():
            for entry in sorted(MEME_ROOT.iterdir()):
                if not entry.is_dir():
                    continue
                files = [
                    p
                    for p in entry.iterdir()
                    if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIX
                ]
                if files:
                    chars.append(entry.name)
                    files_map[entry.name] = files
        self._characters = chars
        self._files_by_character = files_map

    def get_available_characters(self) -> list[str]:
        self._ensure_index()
        return list(self._characters or [])

    def has_available_emojis(self, characters: list[str] | None) -> bool:
        available = self.get_available_characters()
        if not available:
            return False
        if not characters:
            return True
        return any(c in available for c in characters)

    def list_candidate_paths(
        self, characters: list[str] | None, limit: int = 32
    ) -> list[Path]:
        self._ensure_index()
        available = self.get_available_characters()
        if characters:
            pool = [c for c in characters if c in available]
        else:
            pool = available
        paths: list[Path] = []
        for char in pool:
            for p in (self._files_by_character or {}).get(char, []):
                paths.append(p)
                if len(paths) >= limit:
                    return paths
        return paths

    def _clean_sticker_intent(self, text: str) -> str:
        return _STICKER_INTENT_LINE_RE.sub("", text or "").strip()

    def has_sticker_intent(self, text: str) -> bool:
        if not text:
            return False
        return any(
            _STICKER_INTENT_LINE_RE.match(line)
            for line in (text or "").splitlines()
        )

    async def process_sticker_response(
        self,
        text: str,
        ctx: dict | None = None,
        history: list | None = None,
        target_message=None,
        bot_nickname: str | None = None,
    ) -> StickerResult:
        cleaned_text = self._clean_sticker_intent(text or "")
        if not self.has_sticker_intent(text or ""):
            return StickerResult(cleaned_text=cleaned_text, success=False)

        group_id = (ctx or {}).get("groupId") if ctx else None
        cfg = self._config_provider(group_id) if group_id is not None else self._config_provider()
        emoji_cfg = getattr(cfg, "emoji", None)
        if not emoji_cfg or not getattr(emoji_cfg, "enabled", False):
            return StickerResult(cleaned_text=cleaned_text, success=False)

        candidates = self.list_candidate_paths(
            getattr(emoji_cfg, "characters", None) or None
        )
        if not candidates:
            return StickerResult(cleaned_text=cleaned_text, success=False)

        if len(candidates) == 1:
            chosen = candidates[0]
        else:
            chosen = await self._select_by_ai(
                candidates,
                cleaned_text,
                cfg,
                history=history or [],
                target_message=target_message,
                bot_nickname=bot_nickname or "Bot",
            )
            if chosen is None:
                chosen = random.choice(candidates)

        return StickerResult(
            cleaned_text=cleaned_text, success=True, emoji_path=str(chosen)
        )

    async def _select_by_ai(
        self,
        candidates: list[Path],
        assistant_reply: str,
        cfg: Any,
        history: list | None = None,
        target_message=None,
        bot_nickname: str | None = None,
    ) -> Path | None:
        if not self._work_ai:
            return None
        listing = "\n".join(
            f"{i + 1}. [{p.parent.name}] {p.stem}"
            for i, p in enumerate(candidates)
        )
        history_text = "\n".join(
            f"{(bot_nickname if getattr(m, 'role', '') == 'assistant' else getattr(m, 'user_name', None) or 'User')}: {getattr(m, 'content', '')}"
            for m in (history or [])[-20:]
        ) or "(no earlier messages)"

        target_name = (
            getattr(target_message, "user_name", "User") if target_message else "User"
        )
        target_content = (
            getattr(target_message, "content", "") if target_message else ""
        )

        persona = str(getattr(cfg, "persona", "") or "").strip()
        system_prompt = (
            f"You are the sticker selection sub-agent for {bot_nickname or 'Bot'}.\n"
            + (
                f"Identity and persona of {bot_nickname or 'Bot'}:\n{persona}\n"
                if persona
                else ""
            )
            + "The main chat agent has decided to send one sticker in this turn. "
            "Select the single sticker label that best expresses what "
            f"{bot_nickname or 'Bot'} intends to communicate.\n\n"
            "Rules:\n"
            "- Use only the conversation context, the current draft reply, and the sticker labels below.\n"
            "- Sticker labels are text descriptions derived from local filenames. You cannot see the images, so do not invent visual details beyond a label.\n"
            "- Return exactly one valid 1-based index as JSON.\n\n"
            f"Available sticker labels:\n{listing}\n\n"
            'Response format:\n{"selectedIndex":1,"reason":"brief reason"}'
        )
        user_prompt = (
            f"Recent conversation:\n{history_text}\n\n"
            f"Current message from {target_name}:\n{target_content}\n\n"
            f"Current draft reply from {bot_nickname or 'Bot'}:\n{assistant_reply or '(sticker only)'}\n\n"
            f"Choose the most contextually appropriate sticker label for {bot_nickname or 'Bot'} to send now."
        )

        try:
            model = getattr(cfg, "workingModel", None) or ""
            resp = await ai_generate(
                messages=[
                    LLMMessage(
                        role="system", content=[TextPart(text=system_prompt)]
                    ),
                    LLMMessage(
                        role="user", content=[TextPart(text=user_prompt)]
                    ),
                ],
                model=model,
                config=IntentBuilder().config_core(temperature=0.2),
            )
            data = self._extract_json(resp.text or "")
            idx = data.get("selectedIndex") if isinstance(data, dict) else None
            if isinstance(idx, int) and 1 <= idx <= len(candidates):
                logger.info(
                    f"[EmojiAgent] selected [{candidates[idx - 1].parent.name}] "
                    f"{candidates[idx - 1].stem}: {data.get('reason', '')}"
                )
                return candidates[idx - 1]
            # 兼容旧版 ``index`` 字段
            legacy_idx = data.get("index") if isinstance(data, dict) else None
            if isinstance(legacy_idx, int) and 0 <= legacy_idx < len(candidates):
                return candidates[legacy_idx]
        except Exception as e:
            logger.warning(f"[EmojiAgent] select failed: {e}")
        return None

    @staticmethod
    def _extract_json(content: str) -> dict:
        if not content:
            return {}
        try:
            data = json.loads(content)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
