from __future__ import annotations

import os
from pathlib import Path

from zhenxun.configs.path_config import DATA_PATH


LEEKCHAT_DATA_ROOT = Path(DATA_PATH) / "leekchat"


def ensure_leekchat_data_root() -> Path:
    LEEKCHAT_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return LEEKCHAT_DATA_ROOT


def leekchat_data_path(*parts: str | os.PathLike[str]) -> Path:
    target = LEEKCHAT_DATA_ROOT.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


__all__ = [
    "LEEKCHAT_DATA_ROOT",
    "ensure_leekchat_data_root",
    "leekchat_data_path",
]