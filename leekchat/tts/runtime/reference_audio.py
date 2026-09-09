from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional

from ..constants import REFERENCE_AUDIO_DIRNAME, SUPPORTED_LANGS
from ..types import ReferenceAudioEntry, ReferenceAudioManifest, SupportedLang
from ..utils.fs import ensure_dir_async, path_exists, read_json_file, write_json_file


MANIFEST_FILENAME = "reference-audio.json"
MANIFEST_DEFAULTS = ReferenceAudioManifest()


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"\s+", "_", name.strip())
    cleaned = re.sub(r"[^A-Za-z0-9_\-]", "", cleaned)
    cleaned = cleaned[:60]
    return cleaned or "ref"


def normalize_lang(lang: SupportedLang | str) -> SupportedLang:
    lower = str(lang).lower()
    if lower in SUPPORTED_LANGS:
        return lower  # type: ignore[return-value]
    return "zh"


class ReferenceAudioStore:
    def __init__(self, service_data_dir: str) -> None:
        self.audio_dir = os.path.join(service_data_dir, REFERENCE_AUDIO_DIRNAME)
        self.manifest_path = os.path.join(service_data_dir, MANIFEST_FILENAME)
        self._cache: Optional[ReferenceAudioManifest] = None

    async def ensure_ready(self) -> None:
        await ensure_dir_async(self.audio_dir)
        if not await path_exists(self.manifest_path):
            await self._write_manifest(ReferenceAudioManifest())

    async def list(self) -> list[ReferenceAudioEntry]:
        manifest = await self._read_manifest()
        return sorted(manifest.entries.values(), key=lambda e: e.createdAt)

    async def get(self, name: str) -> Optional[ReferenceAudioEntry]:
        manifest = await self._read_manifest()
        return manifest.entries.get(name)

    async def add(
        self,
        *,
        name: str,
        source_file: str,
        prompt_text: str,
        lang: SupportedLang,
    ) -> ReferenceAudioEntry:
        await self.ensure_ready()
        manifest = await self._read_manifest()
        ext = os.path.splitext(source_file)[1].lower() or ".wav"
        safe_name = sanitize_filename(name)
        file_name = f"{safe_name}{ext}"
        target_path = os.path.join(self.audio_dir, file_name)

        try:
            shutil.copyfile(source_file, target_path)
        except OSError as exc:
            raise RuntimeError(f"复制参考音频失败 {source_file}: {exc}") from exc

        now = int(__import__("time").time() * 1000)
        entry = ReferenceAudioEntry(
            name=safe_name,
            fileName=file_name,
            promptText=prompt_text,
            lang=normalize_lang(lang),
            createdAt=manifest.entries[safe_name].createdAt if safe_name in manifest.entries else now,
            updatedAt=now,
        )
        manifest.entries[safe_name] = entry
        await self._write_manifest(manifest)
        return entry

    async def remove(self, name: str) -> bool:
        await self.ensure_ready()
        manifest = await self._read_manifest()
        entry = manifest.entries.get(name)
        if not entry:
            return False
        file_path = os.path.join(self.audio_dir, entry.fileName)
        try:
            Path(file_path).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        del manifest.entries[name]
        await self._write_manifest(manifest)
        return True

    async def resolve_audio_path(self, name: str) -> Optional[str]:
        entry = await self.get(name)
        if not entry:
            return None
        return os.path.join(self.audio_dir, entry.fileName)

    async def _read_manifest(self) -> ReferenceAudioManifest:
        if self._cache is not None:
            return self._cache
        data = await read_json_file(self.manifest_path)
        if not data or not isinstance(data, dict):
            data = {}
        entries_raw = data.get("entries", {})
        if not isinstance(entries_raw, dict):
            entries_raw = {}
        entries: dict[str, ReferenceAudioEntry] = {}
        for k, v in entries_raw.items():
            if not isinstance(v, dict):
                continue
            try:
                entries[k] = ReferenceAudioEntry(
                    name=v.get("name", k),
                    fileName=v.get("fileName", f"{k}.wav"),
                    promptText=v.get("promptText", ""),
                    lang=normalize_lang(v.get("lang", "zh")),
                    createdAt=int(v.get("createdAt", 0)),
                    updatedAt=int(v.get("updatedAt", 0)),
                )
            except (TypeError, ValueError):
                continue
        self._cache = ReferenceAudioManifest(
            schemaVersion=int(data.get("schemaVersion", 1)), entries=entries
        )
        return self._cache

    async def _write_manifest(self, manifest: ReferenceAudioManifest) -> None:
        self._cache = manifest
        await ensure_dir_async(os.path.dirname(self.manifest_path))
        payload = {
            "schemaVersion": manifest.schemaVersion,
            "entries": {
                name: {
                    "name": e.name,
                    "fileName": e.fileName,
                    "promptText": e.promptText,
                    "lang": e.lang,
                    "createdAt": e.createdAt,
                    "updatedAt": e.updatedAt,
                }
                for name, e in manifest.entries.items()
            },
        }
        await write_json_file(self.manifest_path, payload)