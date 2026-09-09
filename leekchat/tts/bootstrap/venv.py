from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..utils.fs import ensure_dir_async, path_exists
from ..utils.log import info, warn
from ..utils.process import run_command
from .python import PythonInfo


@dataclass
class VenvInfo:
    dir: str
    python_bin: str
    pip_bin: str


def _venv_python(venv_dir: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python3")


def _venv_pip(venv_dir: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "pip.exe")
    return os.path.join(venv_dir, "bin", "pip")


def _pip_config_path(venv_dir: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_dir, "pip.ini")
    return os.path.join(venv_dir, "pip.conf")


async def _ensure_pip(python_bin: str) -> None:
    res = await run_command(python_bin, ["-m", "pip", "--version"])
    if res["code"] in (0, None):
        return
    warn("venv 中未检测到 pip，尝试 ensurepip ...")
    ensure = await run_command(python_bin, ["-m", "ensurepip", "--upgrade"])
    if ensure["code"] not in (0, None):
        raise RuntimeError(
            f"虚拟环境内 pip 引导失败: {ensure['stderr'].strip() or ensure['stdout'].strip()}"
        )


async def _write_pip_config(venv_dir: str, index_url: str) -> None:
    if not index_url:
        return
    cfg_path = _pip_config_path(venv_dir)
    body = (
        "[global]\n"
        f"index-url = {index_url}\n"
        "trusted-host = pypi.tuna.tsinghua.edu.cn\n"
    )
    Path(cfg_path).write_text(body, encoding="utf-8")
    info(f"已设置 pip 索引: {index_url}")


async def _set_trusted_host(venv_dir: str) -> None:
    if os.name == "nt":
        return
    cfg = os.path.join(venv_dir, "pyvenv.cfg")
    try:
        raw = Path(cfg).read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    lines = raw.splitlines()
    if not any(line.startswith("include-system-site-packages") for line in lines):
        with open(cfg, "a", encoding="utf-8") as fh:
            fh.write("include-system-site-packages = false\n")


async def create_venv(
    venv_dir: str, python_info: PythonInfo, pip_index_url: str
) -> VenvInfo:
    if not await path_exists(venv_dir):
        info(f"正在创建虚拟环境 {venv_dir} ...")
        res = await run_command(
            python_info.command, ["-m", "venv", venv_dir]
        )
        if res["code"] not in (0, None):
            raise RuntimeError(
                f"创建虚拟环境失败: {res['stderr'].strip() or res['stdout'].strip()}"
            )

    await ensure_dir_async(venv_dir)
    python_bin = _venv_python(venv_dir)
    pip_bin = _venv_pip(venv_dir)

    await _ensure_pip(python_bin)
    await _write_pip_config(venv_dir, pip_index_url)
    await _set_trusted_host(venv_dir)

    probe = await run_command(python_bin, ["--version"])
    if probe["code"] not in (0, None):
        raise RuntimeError(
            f"虚拟环境 Python 不可用: {probe['stderr'].strip() or probe['stdout'].strip()}"
        )
    info(
        f"虚拟环境就绪: {python_bin} ({probe['stdout'].strip() or probe['stderr'].strip()})"
    )
    return VenvInfo(dir=venv_dir, python_bin=python_bin, pip_bin=pip_bin)