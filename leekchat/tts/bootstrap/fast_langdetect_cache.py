from __future__ import annotations

import os
from pathlib import Path

from ..utils.log import debug

CACHE_REL_PATH = os.path.join(
    "GPT_SoVITS", "pretrained_models", "fast_langdetect"
)


async def ensure_fast_langdetect_cache(repo_dir: str) -> None:
    cache_dir = os.path.join(repo_dir, CACHE_REL_PATH)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    debug(f"fast_langdetect 缓存目录就绪: {cache_dir}")