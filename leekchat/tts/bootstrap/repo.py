from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from ..utils.fs import path_exists
from ..utils.log import info
from ..utils.process import command_exists, run_command


async def ensure_git_available() -> None:
    if not command_exists("git"):
        raise RuntimeError("未检测到 git 命令，请先安装 git")


async def _directory_has_git(dir_path: str) -> bool:
    return await path_exists(Path(dir_path) / ".git")


def is_repo_ready(repo_dir: str) -> bool:
    return Path(repo_dir, "api_v2.py").is_file()


async def ensure_repo_cloned(*, repo_dir: str, remote: str) -> None:
    if await _directory_has_git(repo_dir):
        info(f"GPT-SoVITS 仓库已存在: {repo_dir}")
        return
    if await path_exists(repo_dir):
        try:
            shutil.rmtree(repo_dir)
        except OSError:
            pass

    info(f"正在克隆 GPT-SoVITS (代理: {remote}) ...")
    res = await run_command(
        "git",
        ["clone", "--depth=1", "--single-branch", remote, repo_dir],
        timeout=600,
    )
    if res["code"] not in (0, None):
        raise RuntimeError(
            f"git clone 失败: {res['stderr'].strip() or res['stdout'].strip()}"
        )
    info(f"GPT-SoVITS 仓库就绪: {repo_dir}")