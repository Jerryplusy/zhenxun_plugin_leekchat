from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..constants import RUNTIME_LOG_FILENAME
from ..types import GptSovitsModel
from ..utils.log import debug, error, info, warn
from ..utils.process import _SpawnHandle, spawn_detached
from .models import get_model_selection


@dataclass
class RuntimeHandle:
    handle: _SpawnHandle
    pid: Optional[int]
    log_path: str
    api_base: str
    ready_event: "object"
    started_at: int


def _format_yaml(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _render_section(values: dict[str, object]) -> str:
    return "\n".join(f"  {k}: {_format_yaml(v)}" for k, v in values.items())


def _compose_tts_yaml(
    *,
    bert_base_path: str,
    cnhuhbert_base_path: str,
    t2s_weights: str,
    vits_weights: str,
    device: str,
    is_half: bool,
    version: str,
) -> str:
    values = {
        "bert_base_path": bert_base_path,
        "cnhuhbert_base_path": cnhuhbert_base_path,
        "t2s_weights_path": t2s_weights,
        "vits_weights_path": vits_weights,
        "device": device,
        "is_half": is_half,
        "version": version,
    }
    return (
        "custom:\n"
        + _render_section(values)
        + "\n"
        + f"{version}:\n"
        + _render_section(values)
        + "\n"
    )


async def write_tts_config(
    *,
    repo_dir: str,
    model: GptSovitsModel,
    device: str,
    is_half: bool,
) -> str:
    config_path = os.path.join(
        repo_dir, "GPT_SoVITS", "configs", "tts_infer.yaml"
    )
    selection = get_model_selection(model)
    yaml = _compose_tts_yaml(
        bert_base_path=selection.local_bert_dir,
        cnhuhbert_base_path=selection.local_hubert_dir,
        t2s_weights=selection.local_t2s_path,
        vits_weights=selection.local_vits_path,
        device=device,
        is_half=is_half,
        version=model,
    )
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config_path).write_text(yaml, encoding="utf-8")
    info(f"tts_infer.yaml 已写入 (version={model}, device={device})")
    return config_path


def resolve_log_path(service_data_dir: str) -> str:
    return os.path.join(service_data_dir, RUNTIME_LOG_FILENAME)


def _route_stderr(line: str) -> None:
    stripped = line.strip()
    if stripped.startswith(("ERROR", "CRITICAL", "FATAL", "Traceback")):
        error(f"[gpt-sovits] {line}")
    elif stripped.startswith("WARN"):
        warn(f"[gpt-sovits] {line}")
    else:
        info(f"[gpt-sovits] {line}")


async def start_runtime(
    *,
    repo_dir: str,
    python_bin: str,
    host: str,
    port: int,
    model: GptSovitsModel,
    device: str,
    is_half: bool,
    log_path: str,
    ready_event: "object",
    ready_keyword: str = "Application startup complete",
    ready_timeout_ms: int = 120_000,
    extra_env: Optional[dict[str, str]] = None,
) -> RuntimeHandle:
    config_path = await write_tts_config(
        repo_dir=repo_dir, model=model, device=device, is_half=is_half
    )

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    env: dict[str, str] = {**os.environ, **(extra_env or {}), "PYTHONUNBUFFERED": "1"}

    if device == "cuda":
        env.setdefault("CUDA_VISIBLE_DEVICES", "0")
    if device == "mps":
        env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    info(
        f"正在启动 GPT-SoVITS server ({host}:{port}, device={device}, model={model}) ..."
    )

    args = [
        "api_v2.py",
        "-a",
        host,
        "-p",
        str(port),
        "-c",
        config_path,
    ]

    started_at = time.time()
    last_log_ms = [started_at * 1000]

    def _should_resolve(line: str) -> bool:
        if ready_keyword not in line:
            return False
        now_ms = time.time() * 1000
        return (now_ms - last_log_ms[0]) >= 500

    def _on_stdout(line: str) -> None:
        debug(f"[gpt-sovits] {line}")
        if _should_resolve(line):
            try:
                ready_event.set()
            except Exception:
                pass

    def _on_stderr(line: str) -> None:
        _route_stderr(line)
        if _should_resolve(line):
            try:
                ready_event.set()
            except Exception:
                pass

    handle = spawn_detached(
        python_bin,
        args,
        cwd=repo_dir,
        env=env,
        on_stdout_line=_on_stdout,
        on_stderr_line=_on_stderr,
    )
    return RuntimeHandle(
        handle=handle,
        pid=handle.pid,
        log_path=log_path,
        api_base=f"http://{host}:{port}",
        ready_event=ready_event,
        started_at=int(started_at * 1000),
    )


async def stop_runtime(handle: RuntimeHandle) -> None:
    proc = handle.handle.proc
    if proc.poll() is not None:
        return
    info("正在停止 GPT-SoVITS server ...")
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    info("GPT-SoVITS server 已停止")


def resolve_temp_base(data_dir: str) -> str:
    return os.path.join(data_dir, "temp", "audio")