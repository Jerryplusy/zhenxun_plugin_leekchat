from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def ensure_dir(target: str | Path) -> Path:
    p = Path(target)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def ensure_dir_async(target: str | Path) -> Path:
    return ensure_dir(target)


async def path_exists(target: str | Path) -> bool:
    return Path(target).exists()


async def read_json_file(path: str | Path) -> Any | None:
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def write_json_file(path: str | Path, data: Any) -> None:
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_executable_file(candidate: str | Path) -> bool:
    return Path(candidate).is_file() and os.access(candidate, os.X_OK)