from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from typing import Optional

from ..constants import MIN_RAM_GB
from ..utils.log import info, warn
from ..utils.process import run_command


@dataclass
class DeviceProbe:
    device: str
    gpu_name: Optional[str] = None
    vram_mb: Optional[int] = None
    total_memory_gb: float = 0.0
    reason: str = ""


async def _probe_nvidia_smi() -> dict[str, Optional[str | int]]:
    if not shutil.which("nvidia-smi"):
        return {}
    res = await run_command(
        "nvidia-smi",
        ["--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
    )
    if res["code"] not in (0, None) or not res["stdout"].strip():
        return {}
    first = res["stdout"].strip().splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    name = parts[0] if parts else None
    vram = None
    if len(parts) >= 2 and parts[1]:
        try:
            vram = int(parts[1])
        except ValueError:
            vram = None
    return {"name": name or None, "vram": vram}


def _detect_total_memory_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / 1024 / 1024 / 1024, 2)
    except Exception:
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            pages = os.sysconf("SC_PHYS_PAGES")
            return round((page_size * pages) / 1024 / 1024 / 1024, 2)
        except Exception:
            return 0.0


def _detect_apple_silicon() -> tuple[bool, float]:
    if platform.system() != "Darwin":
        return False, _detect_total_memory_gb()
    arch = platform.machine().lower()
    if arch != "arm64":
        return False, _detect_total_memory_gb()
    try:
        cpu_brand = (
            open("/proc/cpuinfo").read()
            if os.path.exists("/proc/cpuinfo")
            else ""
        )
    except Exception:
        cpu_brand = ""
    is_apple = "Apple" in (platform.processor() or "") or "Apple" in cpu_brand
    return is_apple, _detect_total_memory_gb()


async def probe_device() -> DeviceProbe:
    nvidia = await _probe_nvidia_smi()
    if nvidia.get("name"):
        info(
            f"已选择设备: cuda ({nvidia['name']}"
            + (f", VRAM {nvidia['vram']}MB" if nvidia.get("vram") else "")
            + ")"
        )
        return DeviceProbe(
            device="cuda",
            gpu_name=nvidia.get("name") or None,
            vram_mb=nvidia.get("vram") if isinstance(nvidia.get("vram"), int) else None,
            total_memory_gb=_detect_total_memory_gb(),
            reason="nvidia-smi 报告可用 NVIDIA GPU",
        )

    is_apple, total_gb = _detect_apple_silicon()
    if is_apple:
        info(f"已选择设备: mps (Apple Silicon, {total_gb}GB RAM)")
        return DeviceProbe(
            device="mps",
            total_memory_gb=total_gb,
            reason="Apple Silicon detected",
        )

    total_gb = total_gb or _detect_total_memory_gb()
    if total_gb >= MIN_RAM_GB:
        warn(f"未检测到加速硬件，使用 cpu ({total_gb}GB RAM >= {MIN_RAM_GB}GB)")
        return DeviceProbe(
            device="cpu",
            total_memory_gb=total_gb,
            reason=f"内存 {total_gb}GB 满足 CPU 推理最低要求",
        )

    raise RuntimeError(
        f"未检测到可用加速设备且内存仅 {total_gb}GB < {MIN_RAM_GB}GB，"
        "无法满足 GPT-SoVITS 推理要求"
    )


def infer_half_precision(device: str) -> bool:
    return device == "cuda"