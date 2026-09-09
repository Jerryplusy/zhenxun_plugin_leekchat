from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aiohttp


@dataclass
class HealthCheckResult:
    ok: bool
    reason: str | None = None
    code: int | None = None


async def check_runtime_ready(api_base: str, timeout_ms: int = 5_000) -> HealthCheckResult:
    timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{api_base}/control?command=restart") as resp:
                if resp.status == 400:
                    return HealthCheckResult(ok=True)
                if resp.ok:
                    return HealthCheckResult(ok=True)
                return HealthCheckResult(
                    ok=False, code=resp.status, reason=f"unexpected status {resp.status}"
                )
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        return HealthCheckResult(ok=False, reason=str(exc))