from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from ..constants import BUNDLED_REFERENCE_AUDIOS, REFERENCE_AUDIO_DIRNAME
from ..utils.log import info, warn

if TYPE_CHECKING:
    from ..runtime.reference_audio import ReferenceAudioStore


def _assets_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "assets"


async def ensure_default_reference_audio(
    service_data_dir: str, store: "ReferenceAudioStore"
) -> None:
    audio_dir = Path(service_data_dir) / REFERENCE_AUDIO_DIRNAME
    audio_dir.mkdir(parents=True, exist_ok=True)
    await store.ensure_ready()
    for entry in BUNDLED_REFERENCE_AUDIOS:
        await _register_one(store, audio_dir, entry)


async def _register_one(
    store: "ReferenceAudioStore",
    audio_dir: Path,
    entry,
) -> None:
    asset_path = _assets_dir() / entry.filename
    target_path = audio_dir / entry.filename

    existing = await store.get(entry.name)
    has_file = target_path.exists()

    if existing and has_file:
        return
    if not asset_path.is_file():
        warn(f"未找到内置参考音频资源 {asset_path}")
        return

    if not has_file:
        try:
            shutil.copyfile(asset_path, target_path)
            info(f"已复制内置参考音频 -> {target_path}")
        except OSError as exc:
            warn(f"复制内置参考音频失败 {asset_path}: {exc}")
            return

    await store.add(
        name=entry.name,
        source_file=str(asset_path),
        prompt_text=entry.prompt_text,
        lang=entry.lang,
    )
    info(f"内置参考音频已注册: {entry.name} (lang={entry.lang})")