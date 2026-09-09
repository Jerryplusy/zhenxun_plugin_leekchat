from __future__ import annotations

import os
from pathlib import Path

from ..utils.log import debug, info, warn
from ..utils.process import run_command
from .venv import VenvInfo

MARKER_FILENAME = ".deps_installed"


def _is_success(code: object) -> bool:
    return code in (0, None)


async def _pip_install(
    venv: VenvInfo, args: list[str], *, timeout: float = 1800.0
) -> None:
    res = await run_command(
        venv.python_bin, ["-m", "pip", "install", *args],
        cwd=venv.dir,
        timeout=timeout,
    )
    if not _is_success(res["code"]):
        raise RuntimeError(
            f"pip install {' '.join(args)} 失败: {res['stderr'].strip() or res['stdout'].strip()}"
        )


async def _pip_install_requirements(
    venv: VenvInfo, req_file: str, *, flag: str | None = None, timeout: float = 1800.0
) -> None:
    args = ["install"]
    if flag:
        args.append(flag)
    args += ["-r", req_file]
    res = await run_command(
        venv.python_bin, ["-m", "pip", *args], cwd=venv.dir, timeout=timeout
    )
    if not _is_success(res["code"]):
        raise RuntimeError(
            f"pip install -r {req_file} 失败: {res['stderr'].strip() or res['stdout'].strip()}"
        )


async def _already_installed(venv: VenvInfo) -> bool:
    return (Path(venv.dir) / MARKER_FILENAME).is_file()


async def _mark_installed(venv: VenvInfo) -> None:
    Path(venv.dir, MARKER_FILENAME).write_text(
        __import__("datetime").datetime.now().isoformat(),
        encoding="utf-8",
    )


async def ensure_python_deps(venv: VenvInfo, repo_dir: str) -> None:
    if await _already_installed(venv):
        info("检测到 Python 依赖已安装，跳过 pip install")
        return

    info("正在安装 ffmpeg-python ...")
    await _pip_install(venv, ["ffmpeg-python"], timeout=300)

    info("正在安装 extra-req.txt ...")
    await _pip_install_requirements(
        venv, os.path.join(repo_dir, "extra-req.txt"), flag="--no-deps", timeout=600
    )

    info("正在安装 requirements.txt (大约 5-15 分钟) ...")
    await _pip_install_requirements(venv, os.path.join(repo_dir, "requirements.txt"))

    await _mark_installed(venv)
    info("Python 依赖安装完成")


async def ensure_torchcodec(venv: VenvInfo) -> None:
    probe = await run_command(
        venv.python_bin, ["-c", "import torchcodec"], cwd=venv.dir
    )
    if _is_success(probe["code"]):
        debug("torchcodec 已安装，跳过")
        return
    info("正在安装 torchcodec (torchaudio 2.9+ 内部依赖，否则 TTS 报 TorchCodec is required) ...")
    install = await run_command(
        venv.python_bin, ["-m", "pip", "install", "torchcodec"], cwd=venv.dir
    )
    if not _is_success(install["code"]):
        raise RuntimeError(
            f"torchcodec 安装失败: {install['stderr'].strip() or install['stdout'].strip()}"
        )
    info("torchcodec 安装完成")


async def ensure_huggingface_hub(venv: VenvInfo) -> None:
    probe = await run_command(
        venv.python_bin, ["-c", "import huggingface_hub"], cwd=venv.dir
    )
    if _is_success(probe["code"]):
        return
    info("正在安装 huggingface_hub ...")
    install = await run_command(
        venv.python_bin,
        ["-m", "pip", "install", "huggingface_hub"],
        cwd=venv.dir,
    )
    if not _is_success(install["code"]):
        raise RuntimeError(
            f"huggingface_hub 安装失败: {install['stderr'].strip() or install['stdout'].strip()}"
        )
    info("huggingface_hub 安装完成")


async def ensure_nltk_data(venv: VenvInfo) -> None:
    probe = await run_command(
        venv.python_bin,
        [
            "-c",
            "import nltk; nltk.data.find('taggers/averaged_perceptron_tagger_eng')",
        ],
        cwd=venv.dir,
    )
    if _is_success(probe["code"]):
        debug("NLTK averaged_perceptron_tagger_eng 已存在，跳过")
        return
    info("正在下载 NLTK averaged_perceptron_tagger_eng (g2p_en 英文分词需要)...")
    install = await run_command(
        venv.python_bin,
        [
            "-m",
            "nltk.downloader",
            "averaged_perceptron_tagger_eng",
            "-d",
            f"{venv.dir}/nltk_data",
        ],
        cwd=venv.dir,
    )
    if not _is_success(install["code"]):
        warn(
            f"NLTK 资源下载失败: {install['stderr'].strip() or install['stdout'].strip()}"
        )
    else:
        info("NLTK averaged_perceptron_tagger_eng 下载完成")