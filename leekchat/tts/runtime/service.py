from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Optional

from ..api.client import build_tts_request, post_inference, set_gpt_weights, set_sovits_weights
from ..bootstrap.default_ref_audio import ensure_default_reference_audio
from ..bootstrap.index import BootstrapContext, BootstrapResult, bootstrap
from ..bootstrap.models import get_model_selection
from ..bootstrap.runtime import stop_runtime
from ..constants import DATA_DIR, REPO_DIRNAME
from ..types import (
    BootstrapListener,
    GenerateByTextOptions,
    GenerateByTextResult,
    GptSovitsModel,
    SupportedLang,
    TtsSettings,
    TtsStatus,
)
from ..utils.log import error, info, warn
from .output import default_temp_dir, ensure_output_dir, resolve_output_path, write_bytes
from .reference_audio import ReferenceAudioStore


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE).strip("_")
    cleaned = cleaned[:24]
    return cleaned or "voice"


def _truncate(text: str, limit: int = 40) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _media_ext(media: str) -> str:
    if media == "raw":
        return ".pcm"
    return f".{media}"


def _detect_runtime_lang(text: str, fallback: SupportedLang) -> SupportedLang:
    from .language import detect_lang

    return detect_lang(text, fallback)  # type: ignore[return-value]


class TtsService:
    def __init__(self) -> None:
        self._settings: TtsSettings | None = None
        self._status: TtsStatus | None = None
        self._store: ReferenceAudioStore | None = None
        self._runtime = None
        self._repo_dir: str | None = None
        self._ready_event: asyncio.Event | None = None
        self._bootstrap_task: asyncio.Task | None = None
        self._bootstrap_listeners: list[BootstrapListener] = []
        self._lock = asyncio.Lock()
        self._ready_lock = asyncio.Lock()

    def configure(self, settings_dict: dict) -> None:
        self._settings = TtsSettings.from_dict(settings_dict)
        if self._status is None:
            self._status = self._build_status(self._settings)

    def get_status(self) -> TtsStatus | None:
        if self._status is None:
            return None
        return TtsStatus(**self._status.__dict__)

    def is_bootstrapping(self) -> bool:
        return self._bootstrap_task is not None and not self._bootstrap_task.done()

    def is_ready(self) -> bool:
        return bool(self._status and self._status.ready)

    async def ready(self) -> bool:
        async with self._ready_lock:
            if self.is_ready():
                return True
            if self._bootstrap_task is None:
                return False
            try:
                await asyncio.shield(self._bootstrap_task)
            except Exception:
                return False
        return self.is_ready()

    async def start_bootstrap(self, listener: BootstrapListener | None = None) -> None:
        if self._settings is None:
            raise RuntimeError("TtsService 未初始化配置，请先调用 configure()")
        async with self._lock:
            if self._bootstrap_task is not None and not self._bootstrap_task.done():
                return
            if listener is not None:
                self._bootstrap_listeners.append(listener)
            self._ready_event = asyncio.Event()
            self._status = self._build_status(self._settings, bootstrapping=True)
            self._store = ReferenceAudioStore(str(DATA_DIR))
            self._bootstrap_task = asyncio.create_task(self._run_bootstrap())

    async def wait_until_ready(self, timeout: float | None = None) -> bool:
        if self._bootstrap_task is None:
            return False
        try:
            if timeout:
                await asyncio.wait_for(asyncio.shield(self._bootstrap_task), timeout=timeout)
            else:
                await asyncio.shield(self._bootstrap_task)
        except asyncio.TimeoutError:
            return False
        return self.is_ready()

    async def generate_by_text(self, options: GenerateByTextOptions) -> GenerateByTextResult:
        if not self.is_ready():
            raise RuntimeError(
                f"audio 服务尚未就绪 (status={self.get_status() and self.get_status().__dict__})"
            )
        if not options.text:
            raise RuntimeError("generate_by_text 需要提供 text")

        if options.model and options.model != self._status.model:
            await self.set_active_model(options.model)

        runtime = self._runtime
        store = self._store
        await store.ensure_ready()  # type: ignore[union-attr]

        effective_ref_audio_name = (
            options.refAudioName
            or (
                options.refAudioPath
                and ""
                or (self._settings.defaultRefAudio if self._settings else "")
            )
        ).strip()

        requested_lang = options.textLang or (
            self._settings.defaultLang if self._settings else "zh"
        )
        detected = _detect_runtime_lang(options.text, requested_lang)

        ref_audio_path = await self._resolve_ref_audio_path(
            store=store,
            ref_audio_name=effective_ref_audio_name or None,
            ref_audio_path=options.refAudioPath,
        )
        entry = (
            await store.get(effective_ref_audio_name) if effective_ref_audio_name else None
        )
        prompt_text = options.promptText or (entry.promptText if entry else "") or ""
        prompt_lang = options.promptLang or (entry.lang if entry else detected) or detected

        payload = build_tts_request(
            text=options.text,
            ref_audio_path=ref_audio_path,
            prompt_text=prompt_text,
            prompt_lang=prompt_lang,
            text_lang=detected,
            options=options,
        )

        model_used = self._status.model
        media_ext = _media_ext(options.mediaType or "wav")
        temp_dir = options.outputDir or default_temp_dir()
        await ensure_output_dir(temp_dir)
        file_base = (
            options.fileName
            or f"{int(time.time() * 1000)}_{_slug(options.text)}_{model_used}"
        )
        started_at = int(time.time() * 1000)
        info(
            f"正在推理 (模型={model_used}, lang={detected}, "
            f"refAudio={effective_ref_audio_name or Path(ref_audio_path).name}): "
            f"\"{_truncate(options.text)}\""
        )

        result = await post_inference(
            runtime.api_base, payload, self._settings.inferenceTimeoutMs
        )
        inference_ms = int(time.time() * 1000) - started_at
        out = resolve_output_path(temp_dir, file_base, media_ext)
        await write_bytes(out["filePath"], result.bytes)
        info(
            f"推理完成 -> {out['filePath']} "
            f"({inference_ms}ms, {len(result.bytes) / 1024:.1f} KB)"
        )
        return GenerateByTextResult(
            filePath=out["filePath"],
            fileName=out["fileName"],
            modelUsed=model_used,
            text=options.text,
            inferenceMs=inference_ms,
        )

    async def add_reference_audio(
        self,
        *,
        name: str,
        source_file: str,
        prompt_text: str,
        lang: SupportedLang,
    ):
        if self._store is None:
            self._store = ReferenceAudioStore(str(DATA_DIR))
        entry = await self._store.add(
            name=name,
            source_file=source_file,
            prompt_text=prompt_text,
            lang=lang,
        )
        info(f"已添加参考音频: {entry.name} -> {entry.fileName}")
        return entry

    async def remove_reference_audio(self, name: str) -> bool:
        if self._store is None:
            return False
        ok = await self._store.remove(name)
        if ok:
            info(f"已移除参考音频: {name}")
        return ok

    async def list_reference_audios(self):
        if self._store is None:
            return []
        return await self._store.list()

    async def get_reference_audio(self, name: str):
        if self._store is None:
            return None
        return await self._store.get(name)

    def get_active_model(self) -> GptSovitsModel:
        return self._status.model if self._status else "v2"

    async def set_active_model(self, model: GptSovitsModel) -> None:
        if not self._runtime or not self._repo_dir:
            if self._status:
                self._status = TtsStatus(**{**self._status.__dict__, "model": model})
            return
        if model == self._status.model:
            return
        selection = get_model_selection(model)
        sot = str(Path(self._repo_dir) / selection.local_vits_path)
        gpt = str(Path(self._repo_dir) / selection.local_t2s_path)
        info(f"切换模型到 {model} (Sovits={sot}, GPT={gpt})")
        await set_sovits_weights(self._runtime.api_base, sot)
        await set_gpt_weights(self._runtime.api_base, gpt)
        self._status = TtsStatus(**{**self._status.__dict__, "model": model})
        info(f"模型已切换到 {model}")

    def list_supported_models(self) -> list[GptSovitsModel]:
        return ["v2", "v2Pro", "v2ProPlus", "v4"]

    async def dispose(self) -> None:
        if self._runtime:
            try:
                await stop_runtime(self._runtime)
            except Exception as exc:
                warn(f"停止 GPT-SoVITS 子进程失败: {exc}")
            self._runtime = None
        if self._status:
            self._status = TtsStatus(
                **{**self._status.__dict__, "ready": False, "bootstrapping": False}
            )
        self._bootstrap_listeners.clear()

    async def _run_bootstrap(self) -> None:
        assert self._settings is not None
        try:
            from ..utils.paths import ensure_leekchat_data_root

            ensure_leekchat_data_root()
            await ensure_default_reference_audio(str(DATA_DIR), self._store)  # type: ignore[arg-type]
            ctx = BootstrapContext(
                settings=self._settings,
                service_data_dir=str(DATA_DIR),
                listener=self._dispatch_bootstrap_state,
            )
            result: BootstrapResult = await bootstrap(ctx, self._ready_event)  # type: ignore[arg-type]
            self._runtime = result.runtime
            self._repo_dir = str(DATA_DIR / REPO_DIRNAME)
            self._status = TtsStatus(
                ready=True,
                bootstrapping=False,
                device=result.device.device,
                model=result.model,
                host=self._settings.host,
                port=self._settings.port,
                pid=result.runtime.pid,
                startedAt=result.runtime.started_at,
            )
        except Exception as exc:
            message = str(exc) or repr(exc)
            if self._status:
                self._status = TtsStatus(
                    **{
                        **self._status.__dict__,
                        "ready": False,
                        "bootstrapping": False,
                        "lastError": message,
                    }
                )
            error(f"bootstrap 失败: {message}")

    def _dispatch_bootstrap_state(self, state) -> None:
        for listener in list(self._bootstrap_listeners):
            try:
                listener(state)
            except Exception as exc:
                warn(f"bootstrap listener 调用失败: {exc}")

    def _build_status(
        self, settings: TtsSettings, bootstrapping: bool = True
    ) -> TtsStatus:
        return TtsStatus(
            ready=False,
            bootstrapping=bootstrapping,
            device=None,
            model=settings.model,
            host=settings.host,
            port=settings.port,
        )

    async def _resolve_ref_audio_path(
        self,
        *,
        store: ReferenceAudioStore,
        ref_audio_name: Optional[str],
        ref_audio_path: Optional[str],
    ) -> str:
        if ref_audio_path:
            return ref_audio_path
        if not ref_audio_name:
            raise RuntimeError(
                "generate_by_text 需要提供 refAudioName 或 refAudioPath，至少一个参考音频"
            )
        path = await store.resolve_audio_path(ref_audio_name)
        if not path:
            raise RuntimeError(f"未找到参考音频: {ref_audio_name}")
        return path


_service: TtsService | None = None


def get_tts_service() -> TtsService:
    global _service
    if _service is None:
        _service = TtsService()
    return _service


def reset_tts_service() -> None:
    global _service
    _service = None