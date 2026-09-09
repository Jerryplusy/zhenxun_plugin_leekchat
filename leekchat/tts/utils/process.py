from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from typing import IO, Any, Callable, Optional

from .log import debug, warn

RunResult = dict[str, Any]


@dataclass
class _SpawnHandle:
    proc: subprocess.Popen
    pid: Optional[int]


LineCallback = Callable[[str], None]
ExitCallback = Callable[[int | None, Optional[str]], None]


def command_exists(cmd: str) -> bool:
    from shutil import which

    return which(cmd) is not None


async def run_command(
    cmd: str,
    args: list[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> RunResult:
    proc_env = {**os.environ, **(env or {})}
    try:
        proc = await asyncio.create_subprocess_exec(
            cmd,
            *args,
            cwd=cwd,
            env=proc_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        return {"code": 127, "stdout": "", "stderr": str(exc)}
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return {"code": -1, "stdout": "", "stderr": "timeout"}
    return {
        "code": proc.returncode,
        "stdout": (stdout_b or b"").decode(errors="replace"),
        "stderr": (stderr_b or b"").decode(errors="replace"),
    }


def spawn_detached(
    command: str,
    args: list[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    on_stdout_line: Optional[LineCallback] = None,
    on_stderr_line: Optional[LineCallback] = None,
    on_exit: Optional[ExitCallback] = None,
) -> _SpawnHandle:
    proc_env = {**os.environ, **(env or {})}
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "env": proc_env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    proc = subprocess.Popen([command, *args], **kwargs)
    handle = _SpawnHandle(proc=proc, pid=proc.pid)

    def _drain(stream: Optional[IO[Any]], cb: Optional[LineCallback]) -> None:
        if stream is None:
            return
        try:
            for raw in iter(stream.readline, b""):
                try:
                    line = raw.decode(errors="replace")
                except Exception:
                    line = str(raw)
                line = line.rstrip("\r\n")
                if not line or cb is None:
                    continue
                try:
                    cb(line)
                except Exception as exc:
                    warn(f"line 回调异常: {exc}")
        except Exception as exc:
            debug(f"drain 异常: {exc}")

    def _wait() -> None:
        import threading

        t_out = threading.Thread(
            target=_drain, args=(proc.stdout, on_stdout_line), daemon=True
        )
        t_err = threading.Thread(
            target=_drain, args=(proc.stderr, on_stderr_line), daemon=True
        )
        t_out.start()
        t_err.start()
        rc = proc.wait()
        t_out.join(timeout=1.0)
        t_err.join(timeout=1.0)
        if on_exit:
            try:
                on_exit(rc, None)
            except Exception as exc:
                warn(f"on_exit 回调异常: {exc}")

    threading_mod = __import__("threading")
    threading_mod.Thread(target=_wait, daemon=True).start()
    return handle