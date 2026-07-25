from __future__ import annotations

import asyncio
import time


DEFAULT_DYNAMIC_DELAY = {
    "enabled": True,
    "interactionWindowMs": 60_000,
    "baseDelayMs": 30_000,
    "maxDelayMs": 300_000,
}

DEFAULT_AI_REQUEST_LIMITS = {
    "userRpm": 3,
    "groupRpm": 6,
    "windowMs": 60_000,
}


class RateLimiter:
    def __init__(
        self,
        max_triggers_per_window: int = 5,
        window_ms: int = 60_000,
        dedup_window_ms: int = 30_000,
        group_cooldown_ms: int = 1_000,
    ):
        self.max_triggers_per_window = max_triggers_per_window
        self.window_ms = window_ms
        self.dedup_window_ms = dedup_window_ms
        self.group_cooldown_ms = group_cooldown_ms

        self._user_triggers: dict[int, list[int]] = {}
        self._user_messages: dict[int, list[dict]] = {}
        self._group_last_response: dict[int, int] = {}
        self._group_interactions: dict[int, dict[int, list[int]]] = {}
        self._user_ai_requests: dict[int, list[int]] = {}
        self._group_ai_requests: dict[int, list[int]] = {}

        self._get_config = None
        self._get_queue_length = None
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def set_config_provider(self, provider) -> None:
        self._get_config = provider

    def set_queue_length_getter(self, fn) -> None:
        self._get_queue_length = fn

    def start(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def _dynamic_delay(self, group_id: int | None) -> dict:
        if self._get_config:
            cfg = self._get_config(group_id)
            dd = getattr(cfg, "dynamicDelay", None)
            if dd is not None:
                return dd.model_dump() if hasattr(dd, "model_dump") else dict(dd)
        return DEFAULT_DYNAMIC_DELAY

    def _ai_request_limits(self, group_id: int | None) -> dict:
        if self._get_config:
            cfg = self._get_config(group_id)
            al = getattr(cfg, "aiRequestLimits", None)
            if al is not None:
                return al.model_dump() if hasattr(al, "model_dump") else dict(al)
        return DEFAULT_AI_REQUEST_LIMITS

    def can_process(self, user_id: int, group_id: int | None, content: str) -> bool:
        now = int(time.time() * 1000)
        if group_id:
            last = self._group_last_response.get(group_id)
            if last is not None and now - last < self.group_cooldown_ms:
                return False

        triggers = [t for t in self._user_triggers.get(user_id, []) if now - t < self.window_ms]
        if len(triggers) >= self.max_triggers_per_window:
            return False

        for m in self._user_messages.get(user_id, []):
            if m["content"] == content and now - m["timestamp"] < self.dedup_window_ms:
                return False
        return True

    def record(self, user_id: int, group_id: int | None, content: str) -> None:
        now = int(time.time() * 1000)
        triggers = self._user_triggers.setdefault(user_id, [])
        triggers.append(now)

        msgs = self._user_messages.setdefault(user_id, [])
        msgs.append({"content": content, "timestamp": now})
        if len(msgs) > 3:
            self._user_messages[user_id] = msgs[-3:]

        if group_id is not None:
            self._group_last_response[group_id] = now

    def record_interaction(self, group_id: int, user_id: int) -> None:
        cfg = self._dynamic_delay(group_id)
        if not cfg.get("enabled", False):
            return
        now = int(time.time() * 1000)
        window = cfg["interactionWindowMs"]
        users = self._group_interactions.setdefault(group_id, {})
        timestamps = [t for t in users.get(user_id, []) if now - t < window]
        timestamps.append(now)
        users[user_id] = timestamps

    def can_run_ai_request(self, user_id: int | None, group_id: int | None) -> bool:
        now = int(time.time() * 1000)
        limits = self._ai_request_limits(group_id)

        if isinstance(user_id, int):
            reqs = [t for t in self._user_ai_requests.get(user_id, []) if now - t < limits["windowMs"]]
            if len(reqs) >= limits["userRpm"]:
                return False

        if isinstance(group_id, int):
            reqs = [t for t in self._group_ai_requests.get(group_id, []) if now - t < limits["windowMs"]]
            if len(reqs) >= limits["groupRpm"]:
                return False
        return True

    def record_ai_request(self, user_id: int | None, group_id: int | None) -> None:
        now = int(time.time() * 1000)
        window = self._ai_request_limits(group_id)["windowMs"]
        if isinstance(user_id, int):
            reqs = [t for t in self._user_ai_requests.get(user_id, []) if now - t < window]
            reqs.append(now)
            self._user_ai_requests[user_id] = reqs
        if isinstance(group_id, int):
            reqs = [t for t in self._group_ai_requests.get(group_id, []) if now - t < window]
            reqs.append(now)
            self._group_ai_requests[group_id] = reqs

    def get_interaction_count(self, group_id: int) -> int:
        if self._get_queue_length and self._get_queue_length(group_id) > 0:
            return self._get_queue_length(group_id)

        now = int(time.time() * 1000)
        cfg = self._dynamic_delay(group_id)
        window = cfg["interactionWindowMs"]
        users = self._group_interactions.get(group_id, {})
        count = 0
        for _, timestamps in users.items():
            if any(now - t < window for t in timestamps):
                count += 1
        return count

    def calculate_delay(self, group_id: int) -> int:
        cfg = self._dynamic_delay(group_id)
        if not cfg.get("enabled", False):
            return 0
        interaction_count = self.get_interaction_count(group_id)
        if interaction_count <= 1:
            return 0
        delay = (interaction_count - 1) * cfg["baseDelayMs"]
        return min(delay, cfg["maxDelayMs"])

    def get_delay_info(self, group_id: int) -> dict:
        interaction_count = self.get_interaction_count(group_id)
        delay_ms = self.calculate_delay(group_id)
        return {
            "delayMs": delay_ms,
            "interactionCount": interaction_count,
            "shouldDelay": delay_ms > 0,
        }

    def clear_group_interactions(self, group_id: int) -> None:
        self._group_interactions.pop(group_id, None)

    async def _periodic_cleanup(self) -> None:
        try:
            while True:
                await asyncio.sleep(300)
                self.cleanup()
        except asyncio.CancelledError:
            return

    def cleanup(self) -> None:
        now = int(time.time() * 1000)
        for user_id, triggers in list(self._user_triggers.items()):
            valid = [t for t in triggers if now - t < self.window_ms]
            if not valid:
                self._user_triggers.pop(user_id, None)
            else:
                self._user_triggers[user_id] = valid

        for user_id, messages in list(self._user_messages.items()):
            valid = [m for m in messages if now - m["timestamp"] < self.dedup_window_ms]
            if not valid:
                self._user_messages.pop(user_id, None)
            else:
                self._user_messages[user_id] = valid

        for group_id, ts in list(self._group_last_response.items()):
            if now - ts > self.group_cooldown_ms * 10:
                self._group_last_response.pop(group_id, None)

        for group_id, users in list(self._group_interactions.items()):
            window = self._dynamic_delay(group_id)["interactionWindowMs"]
            active = False
            for user_id, timestamps in list(users.items()):
                valid = [t for t in timestamps if now - t < window]
                if not valid:
                    users.pop(user_id, None)
                else:
                    users[user_id] = valid
                    active = True
            if not active:
                self._group_interactions.pop(group_id, None)