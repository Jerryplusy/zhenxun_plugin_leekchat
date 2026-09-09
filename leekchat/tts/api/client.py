from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import aiohttp

from ..types import GenerateByTextOptions, SupportedLang


@dataclass
class TtsRequestPayload:
    text: str
    text_lang: str
    ref_audio_path: str
    prompt_text: str
    prompt_lang: str
    text_split_method: str
    top_k: int
    top_p: float
    temperature: float
    speed_factor: float
    media_type: str
    streaming_mode: bool
    parallel_infer: bool
    seed: int


@dataclass
class InferenceResult:
    bytes: bytes
    content_type: str
    duration_ms: int


def build_tts_request(
    *,
    text: str,
    ref_audio_path: str,
    prompt_text: str,
    prompt_lang: SupportedLang | str,
    text_lang: SupportedLang | str,
    options: GenerateByTextOptions,
) -> TtsRequestPayload:
    return TtsRequestPayload(
        text=text,
        text_lang=str(text_lang).lower(),
        ref_audio_path=ref_audio_path,
        prompt_text=prompt_text,
        prompt_lang=str(prompt_lang).lower(),
        text_split_method=options.textSplitMethod or "cut5",
        top_k=options.topK if options.topK is not None else 15,
        top_p=options.topP if options.topP is not None else 1.0,
        temperature=options.temperature if options.temperature is not None else 1.0,
        speed_factor=options.speedFactor if options.speedFactor is not None else 1.0,
        media_type=options.mediaType or "wav",
        streaming_mode=bool(options.streaming) if options.streaming is not None else False,
        parallel_infer=bool(options.parallelInfer) if options.parallelInfer is not None else True,
        seed=options.seed if options.seed is not None else -1,
    )


async def post_inference(
    api_base: str, payload: TtsRequestPayload, timeout_ms: int
) -> InferenceResult:
    timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000)
    started = asyncio.get_event_loop().time()
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            f"{api_base}/tts", json=payload.__dict__
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"TTS 接口返回 {resp.status}: {text}")
            content_type = resp.headers.get("content-type") or "audio/wav"
            data = await resp.read()
    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
    return InferenceResult(bytes=data, content_type=content_type, duration_ms=duration_ms)


async def set_sovits_weights(api_base: str, weights_path: str) -> None:
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(
            f"{api_base}/set_sovits_weights",
            params={"weights_path": weights_path},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(
                    f"set_sovits_weights 失败 ({resp.status}): {text}"
                )


async def set_gpt_weights(api_base: str, weights_path: str) -> None:
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(
            f"{api_base}/set_gpt_weights",
            params={"weights_path": weights_path},
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(
                    f"set_gpt_weights 失败 ({resp.status}): {text}"
                )