from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from ..constants import (
    BOOTSTRAP_READY_TIMEOUT_MS,
    REPO_DIRNAME,
    RUNTIME_STARTUP_TIMEOUT_MS,
    VENV_DIRNAME,
)
from ..types import BootstrapListener, BootstrapState, GptSovitsModel, TtsSettings
from ..utils.log import error, info
from .default_ref_audio import ensure_default_reference_audio
from .deps import ensure_huggingface_hub, ensure_nltk_data, ensure_python_deps, ensure_torchcodec
from .device import DeviceProbe, infer_half_precision, probe_device
from .fast_langdetect_cache import ensure_fast_langdetect_cache
from .models import ensure_base_pretrained, ensure_g2pw_model, ensure_model_weights
from .python import PythonInfo, ensure_pip, select_python
from .repo import ensure_git_available, ensure_repo_cloned, is_repo_ready
from .runtime import RuntimeHandle, resolve_log_path, start_runtime
from .source_patch import ensure_source_patch
from .venv import VenvInfo, create_venv


@dataclass
class BootstrapContext:
    settings: TtsSettings
    service_data_dir: str
    listener: Optional[BootstrapListener] = None


@dataclass
class BootstrapResult:
    device: DeviceProbe
    python: PythonInfo
    venv: VenvInfo
    runtime: RuntimeHandle
    model: GptSovitsModel


async def bootstrap(ctx: BootstrapContext, ready_event: asyncio.Event) -> BootstrapResult:
    settings = ctx.settings
    update = _make_updater(ctx.listener)

    device: DeviceProbe
    try:
        update("device", "正在检测运行设备 (NVIDIA / Apple Silicon / CPU)...")
        device = await probe_device()
    except Exception as exc:
        update("error", f"设备检测失败: {exc}")
        raise

    update("python", "正在选择系统 Python ...")
    python = await select_python(settings.pythonVersion)
    await ensure_pip(python.command)

    repo_dir = _safe_join(ctx.service_data_dir, REPO_DIRNAME)
    venv_dir = _safe_join(ctx.service_data_dir, VENV_DIRNAME)

    update("venv", "正在创建 Python 虚拟环境 ...")
    venv = await create_venv(venv_dir, python, settings.pipIndexUrl)

    update("repo", "正在拉取 GPT-SoVITS 仓库 ...")
    await ensure_git_available()
    await ensure_repo_cloned(repo_dir=repo_dir, remote=settings.gitRemote)
    await ensure_source_patch(repo_dir, ctx.service_data_dir)
    await ensure_fast_langdetect_cache(repo_dir)

    update("models", "正在准备预训练模型 ...")
    await ensure_base_pretrained(repo_dir, settings.hfMirror)
    await ensure_model_weights(repo_dir, settings.model, settings.hfMirror)
    if settings.model == "v2":
        update("models", "正在准备 G2PW 模型 ...")
        await ensure_g2pw_model(repo_dir, settings.hfMirror)

    update("deps", "正在安装 Python 依赖 (可能耗时 5-15 分钟)...")
    await ensure_python_deps(venv, repo_dir)

    update("deps", "正在确保 huggingface_hub 已安装 ...")
    await ensure_huggingface_hub(venv)

    update("deps", "正在确保 torchcodec 已安装 (torchaudio 2.9+ 必需)...")
    await ensure_torchcodec(venv)

    update("deps", "正在确保 NLTK 分词资源已就绪 ...")
    await ensure_nltk_data(venv)

    final_device = device.device if settings.device == "auto" else settings.device
    is_half = bool(
        settings.isHalf
        and infer_half_precision(final_device)
        and final_device == "cuda"
    )

    log_path = resolve_log_path(ctx.service_data_dir)
    if not is_repo_ready(repo_dir):
        raise RuntimeError(f"仓库不完整: {repo_dir}")

    update("runtime", "正在启动 GPT-SoVITS server ...")
    runtime = await start_runtime(
        repo_dir=repo_dir,
        python_bin=venv.python_bin,
        host=settings.host,
        port=settings.port,
        model=settings.model,
        device=final_device,
        is_half=is_half,
        log_path=log_path,
        ready_event=ready_event,
        ready_timeout_ms=RUNTIME_STARTUP_TIMEOUT_MS,
        extra_env={"HF_ENDPOINT": settings.hfMirror},
    )

    try:
        await asyncio.wait_for(
            ready_event.wait(), timeout=RUNTIME_STARTUP_TIMEOUT_MS / 1000
        )
    except asyncio.TimeoutError as exc:
        update("error", "GPT-SoVITS server 启动超时")
        raise RuntimeError("GPT-SoVITS server 启动超时") from exc

    update(
        "ready",
        f"GPT-SoVITS 服务就绪 (端口 {settings.port}, 设备 {final_device})",
        ready=True,
    )
    return BootstrapResult(
        device=device,
        python=python,
        venv=venv,
        runtime=runtime,
        model=settings.model,
    )


def _make_updater(listener: Optional[BootstrapListener]):
    def update(phase: str, message: str, ready: bool = False) -> None:
        state = BootstrapState(phase=phase, message=message, ready=ready)
        if listener:
            try:
                res = listener(state)
            except Exception as exc:
                info(f"bootstrap listener 调用失败: {exc}")
                res = None
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        if phase == "error":
            error(message)
        else:
            info(message)

    return update


def _safe_join(*parts: str) -> str:
    from os.path import join

    return join(*parts)


def bound_bootstrap_timeout() -> int:
    return BOOTSTRAP_READY_TIMEOUT_MS