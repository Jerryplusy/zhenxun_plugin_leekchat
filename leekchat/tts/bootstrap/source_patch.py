from __future__ import annotations

import os
from pathlib import Path

from ..utils.log import info, warn

PATCH_MARKER_FILENAME = ".source-patched"
PATCH_TARGET_REL_PATH = os.path.join(
    "GPT_SoVITS", "TTS_infer_pack", "TTS.py"
)
OLD_DURATION_GUARD = "> 160000"
NEW_DURATION_GUARD = "> 320000"


async def ensure_source_patch(repo_dir: str, service_data_dir: str) -> None:
    marker_path = os.path.join(service_data_dir, PATCH_MARKER_FILENAME)
    if Path(marker_path).is_file():
        return

    target_path = os.path.join(repo_dir, PATCH_TARGET_REL_PATH)
    if not Path(target_path).is_file():
        warn(f"源码补丁目标文件不存在，跳过: {target_path}")
        return

    try:
        original = Path(target_path).read_text(encoding="utf-8")
    except OSError as exc:
        warn(f"读取源码失败: {exc}")
        return

    if (
        NEW_DURATION_GUARD in original
        and OLD_DURATION_GUARD not in original
    ):
        Path(marker_path).write_text(
            __import__("datetime").datetime.now().isoformat(), encoding="utf-8"
        )
        return

    if OLD_DURATION_GUARD not in original:
        warn(
            f"未在 {PATCH_TARGET_REL_PATH} 找到锚点 \"{OLD_DURATION_GUARD}\"，"
            "GPT-SoVITS 源码可能已变更，跳过 monkey patch"
        )
        return

    patched = original.replace(OLD_DURATION_GUARD, NEW_DURATION_GUARD)
    Path(target_path).write_text(patched, encoding="utf-8")
    Path(marker_path).write_text(
        __import__("datetime").datetime.now().isoformat(), encoding="utf-8"
    )
    info(
        f"已对 GPT-SoVITS 源码打猴子补丁: 参考音频时长上限 10s -> 20s "
        f"(锚点 {OLD_DURATION_GUARD} -> {NEW_DURATION_GUARD})"
    )