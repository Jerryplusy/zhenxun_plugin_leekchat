from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import Optional

from ..constants import DATA_DIR, TEMP_AUDIO_DIRNAME


def default_temp_dir() -> str:
    return str(DATA_DIR / TEMP_AUDIO_DIRNAME)


def resolve_output_path(
    preferred_dir: Optional[str], preferred_name: Optional[str], extension: str
) -> dict[str, str]:
    target_dir = preferred_dir or default_temp_dir()
    return build_target(target_dir, preferred_name, extension)


async def ensure_output_dir(dir_path: str) -> None:
    Path(dir_path).mkdir(parents=True, exist_ok=True)


async def write_bytes(file_path: str, data: bytes) -> None:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).write_bytes(data)


def build_target(
    dir_path: str, preferred_name: Optional[str], extension: str
) -> dict[str, str]:
    ext = extension if extension.startswith(".") else f".{extension}"
    safe = _sanitize(preferred_name) or f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    file_name = safe if safe.endswith(ext) else f"{safe}{ext}"
    return {"dir": dir_path, "filePath": str(Path(dir_path) / file_name), "fileName": file_name}


def _sanitize(input_str: Optional[str]) -> Optional[str]:
    if not input_str:
        return None
    cleaned = re.sub(r"\s+", "_", input_str.strip())
    cleaned = re.sub(r"[^A-Za-z0-9_.\-]", "", cleaned)
    cleaned = cleaned[:80]
    return cleaned or None