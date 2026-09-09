from __future__ import annotations

import asyncio
import os
from typing import Optional

from .log import info, warn
from .process import command_exists, run_command


def _parse_pid(line: str) -> Optional[int]:
    line = line.strip()
    if not line:
        return None
    try:
        pid = int(line)
    except ValueError:
        return None
    if pid <= 0:
        return None
    return pid


async def _list_listening_pids_via_lsof(port: int) -> list[int]:
    if not command_exists("lsof"):
        return []
    res = await run_command(
        "lsof", ["-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]
    )
    if res["code"] not in (0, None):
        return []
    pids: list[int] = []
    for line in res["stdout"].splitlines():
        pid = _parse_pid(line)
        if pid:
            pids.append(pid)
    return pids


async def _list_listening_pids_via_netstat(port: int) -> list[int]:
    if not command_exists("netstat"):
        return []
    res = await run_command("netstat", ["-ano", "-p", "TCP"])
    pids: list[int] = []
    for line in res["stdout"].splitlines():
        cols = line.strip().split()
        if len(cols) < 5:
            continue
        if cols[0].upper() != "TCP":
            continue
        if not cols[3].upper().startswith("LISTENING"):
            continue
        local = cols[1]
        if ":" not in local:
            continue
        try:
            local_port = int(local.rsplit(":", 1)[1])
        except ValueError:
            continue
        if local_port != port:
            continue
        pid = _parse_pid(cols[4])
        if pid:
            pids.append(pid)
    return pids


def _send_signal(pid: int, sig: int) -> bool:
    if pid == os.getpid():
        return False
    try:
        os.kill(pid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


async def free_port(port: int, grace_ms: int = 1500) -> dict[str, list[int]]:
    if os.name == "nt":
        initial = await _list_listening_pids_via_netstat(port)
    else:
        initial = await _list_listening_pids_via_lsof(port) or await _list_listening_pids_via_netstat(port)
    occupied = [pid for pid in initial if pid != os.getpid()]
    if not occupied:
        return {"killedPids": [], "remainingPids": []}
    warn(f"端口 {port} 被占用，进程 PID: {','.join(str(p) for p in occupied)}，正在结束...")

    killed: list[int] = []
    for pid in occupied:
        if _send_signal(pid, 15):
            killed.append(pid)
    if killed:
        await asyncio.sleep(grace_ms / 1000)

    if os.name == "nt":
        remaining = await _list_listening_pids_via_netstat(port)
    else:
        remaining = await _list_listening_pids_via_lsof(port) or await _list_listening_pids_via_netstat(port)
    remaining = [pid for pid in remaining if pid != os.getpid()]

    if remaining:
        warn(
            f"端口 {port} 仍被占用 (PID: {','.join(str(p) for p in remaining)})，发送 SIGKILL 强制结束..."
        )
        for pid in remaining:
            if _send_signal(pid, 9):
                killed.append(pid)
        await asyncio.sleep(0.3)
        if os.name == "nt":
            remaining = await _list_listening_pids_via_netstat(port)
        else:
            remaining = await _list_listening_pids_via_lsof(port) or await _list_listening_pids_via_netstat(port)
        remaining = [pid for pid in remaining if pid != os.getpid()]

    if remaining:
        warn(
            f"端口 {port} 仍被占用，无法结束进程 PID: {','.join(str(p) for p in remaining)}"
        )
    elif killed:
        info(f"端口 {port} 已释放")

    return {"killedPids": killed, "remainingPids": remaining}