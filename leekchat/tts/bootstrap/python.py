from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

from ..constants import SUPPORTED_PY_VERSIONS, VENV_PY_MAX_EXCLUSIVE, VENV_PY_MIN
from ..utils.log import info, warn
from ..utils.process import run_command


@dataclass
class PythonInfo:
    command: str
    version: str
    raw: str
    source: str


def _candidates_darwin() -> list[str]:
    home = os.path.expanduser("~")
    return [
        "python3",
        "python",
        "/opt/homebrew/bin/python3",
        "/opt/homebrew/bin/python3.10",
        "/opt/homebrew/bin/python3.11",
        "/opt/homebrew/bin/python3.12",
        "/usr/local/bin/python3",
        "/usr/local/bin/python3.10",
        "/usr/local/bin/python3.11",
        "/usr/local/bin/python3.12",
        "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
        "/opt/miniconda3/bin/python3",
        "/opt/miniconda3/bin/python",
        "/opt/anaconda3/bin/python3",
        "/opt/anaconda3/bin/python",
        f"{home}/miniconda3/bin/python3",
        f"{home}/miniconda3/bin/python",
        f"{home}/anaconda3/bin/python3",
        f"{home}/anaconda3/bin/python",
        "/usr/bin/python3",
    ]


def _candidates_linux() -> list[str]:
    home = os.path.expanduser("~")
    return [
        "python3",
        "python",
        "/usr/bin/python3",
        "/usr/bin/python3.10",
        "/usr/bin/python3.11",
        "/usr/bin/python3.12",
        "/usr/local/bin/python3",
        "/usr/local/bin/python3.10",
        "/usr/local/bin/python3.11",
        "/usr/local/bin/python3.12",
        f"{home}/miniconda3/bin/python3",
        f"{home}/anaconda3/bin/python3",
    ]


def _candidates_win() -> list[str]:
    return ["py", "python3", "python"]


def _parse_major_minor(raw: str) -> list[int]:
    match = re.search(r"Python\s+(\d+)\.(\d+)", raw, re.IGNORECASE)
    if not match:
        return []
    return [int(match.group(1)), int(match.group(2))]


def _is_version_supported(version: list[int]) -> bool:
    if len(version) < 2:
        return False
    major, minor = version
    if major != 3:
        return False
    return (
        (minor, 0) >= VENV_PY_MIN
        and (minor, 0) < VENV_PY_MAX_EXCLUSIVE
    )


async def _probe(cmd: str) -> Optional[PythonInfo]:
    res = await run_command(cmd, ["--version"])
    if res["code"] not in (0, None):
        return None
    raw = (res["stdout"] + res["stderr"]).strip()
    version = _parse_major_minor(raw)
    if not _is_version_supported(version):
        return None
    source = "路径 " + cmd if "/" in cmd or "\\" in cmd else "PATH 中的 python"
    return PythonInfo(
        command=cmd,
        version=f"{version[0]}.{version[1]}",
        raw=raw,
        source=source,
    )


async def list_available_pythons() -> list[PythonInfo]:
    if sys.platform == "win32":
        candidates = _candidates_win()
    elif sys.platform == "darwin":
        candidates = _candidates_darwin()
    else:
        candidates = _candidates_linux()

    seen: set[str] = set()
    results: list[PythonInfo] = []
    for cmd in candidates:
        if cmd in seen:
            continue
        seen.add(cmd)
        info_obj = await _probe(cmd)
        if info_obj:
            results.append(info_obj)
    return results


async def select_python(preferred_version: str) -> PythonInfo:
    candidates = await list_available_pythons()
    if not candidates:
        raise RuntimeError(
            "未在系统找到可用的 Python (3.10 - 3.12)，请安装 Python 3.10/3.11/3.12 后重启服务"
        )
    if preferred_version not in SUPPORTED_PY_VERSIONS:
        preferred_version = "3.10"
    try:
        pref_major, pref_minor = (int(x) for x in preferred_version.split("."))
    except ValueError:
        pref_major, pref_minor = 3, 10
    exact = next(
        (c for c in candidates if c.version == f"{pref_major}.{pref_minor}"), None
    )
    if exact:
        info(f"已选择 Python: {exact.command} ({exact.version}, 来自 {exact.source})")
        return exact
    listing = "\n".join(f"  - {c.command} ({c.version}, {c.source})" for c in candidates)
    raise RuntimeError(
        f"系统未找到 Python {preferred_version}。可用的 Python:\n{listing}\n"
        f"请安装 Python {preferred_version} 或在 tts 配置中切换到已安装的版本"
    )


async def ensure_pip(python_cmd: str) -> None:
    res = await run_command(python_cmd, ["-m", "pip", "--version"])
    if res["code"] in (0, None):
        return
    warn("未检测到 pip，尝试通过 ensurepip 引导安装 ...")
    ensure = await run_command(python_cmd, ["-m", "ensurepip", "--upgrade"])
    if ensure["code"] not in (0, None):
        raise RuntimeError(
            f"Python pip 未安装且 ensurepip 失败: {ensure['stderr'].strip() or ensure['stdout'].strip()}"
        )