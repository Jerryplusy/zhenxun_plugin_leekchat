from __future__ import annotations

import time

from zhenxun.services.log import logger

from ..models import ChatSession


class SessionManager:
    def __init__(self, max_size: int = 100):
        self._cache: dict[str, dict] = {}
        self._max_size = max_size

    async def get_or_create(self, session_id: str, type_: str, target_id: int) -> dict:
        if session_id in self._cache:
            return self._touch(session_id)

        existing = await ChatSession.get_or_none(id=session_id)
        if existing:
            data = self._to_dict(existing)
            self._add_to_cache(session_id, data)
            return data

        now = int(time.time() * 1000)
        await ChatSession.create(
            id=session_id,
            type=type_,
            target_id=target_id,
            created_at=now,
            updated_at=now,
            compressed_context=None,
        )
        data = {
            "id": session_id,
            "type": type_,
            "target_id": target_id,
            "created_at": now,
            "updated_at": now,
            "compressed_context": None,
        }
        self._add_to_cache(session_id, data)
        return data

    async def get(self, session_id: str) -> dict | None:
        if session_id in self._cache:
            return self._touch(session_id)
        existing = await ChatSession.get_or_none(id=session_id)
        if existing:
            data = self._to_dict(existing)
            self._add_to_cache(session_id, data)
            return data
        return None

    async def reset_bot_messages(self, session_id: str) -> None:
        from ..models import ChatMessage

        await ChatMessage.filter(session_id=session_id, role="assistant").delete()
        logger.info(f"reset bot messages for session {session_id}")

    def _touch(self, session_id: str) -> dict:
        data = self._cache[session_id]
        data["updated_at"] = int(time.time() * 1000)
        self._cache.pop(session_id, None)
        self._cache[session_id] = data
        return data

    def _add_to_cache(self, session_id: str, data: dict) -> None:
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key, None)
        self._cache[session_id] = data

    @staticmethod
    def _to_dict(record: ChatSession) -> dict:
        return {
            "id": record.id,
            "type": record.type,
            "target_id": record.target_id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "compressed_context": record.compressed_context,
        }