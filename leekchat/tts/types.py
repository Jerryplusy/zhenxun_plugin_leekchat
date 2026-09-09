from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal, Optional

from .constants import (
    DEFAULT_GIT_REMOTE,
    DEFAULT_HF_MIRROR,
    DEFAULT_HOST,
    DEFAULT_HUGGINGFACE_REPO,
    DEFAULT_INFERENCE_TIMEOUT_MS,
    DEFAULT_IS_HALF,
    DEFAULT_PIP_INDEX_URL,
    DEFAULT_PORT,
    DEFAULT_PYTHON_VERSION,
    DEFAULT_TEXT_SPLIT_METHOD,
    SUPPORTED_LANGS,
    SUPPORTED_MODELS,
    SUPPORTED_TEXT_SPLIT_METHODS,
)

GptSovitsModel = Literal["v2", "v2Pro", "v2ProPlus", "v4"]
SupportedLang = Literal["zh", "en", "ja", "ko", "yue"]
TextSplitMethod = Literal[
    "cut0",
    "cut1",
    "cut2",
    "cut3",
    "cut4",
    "cut5",
    "english_cut1",
    "english_cut2",
    "japan_cut1",
    "japan_cut2",
    "japan_cut3",
    "korean_cut1",
    "yue_cut1",
    "auto",
]
ComputeDevice = Literal["cuda", "mps", "cpu"]


@dataclass
class TtsSettings:
    model: GptSovitsModel = "v2"
    device: Literal["cuda", "mps", "cpu", "auto"] = "auto"
    defaultLang: SupportedLang = "zh"
    defaultRefAudio: str = "miku-jp"

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    pythonVersion: str = DEFAULT_PYTHON_VERSION
    pipIndexUrl: str = DEFAULT_PIP_INDEX_URL
    hfMirror: str = DEFAULT_HF_MIRROR
    gitRemote: str = DEFAULT_GIT_REMOTE
    huggingfaceRepo: str = DEFAULT_HUGGINGFACE_REPO
    defaultTextSplitMethod: TextSplitMethod = DEFAULT_TEXT_SPLIT_METHOD
    inferenceTimeoutMs: int = DEFAULT_INFERENCE_TIMEOUT_MS
    isHalf: bool = DEFAULT_IS_HALF

    @classmethod
    def from_dict(cls, data: dict) -> "TtsSettings":
        return cls(
            model=data.get("model", "v2"),
            device=data.get("device", "auto"),
            host=data.get("host", DEFAULT_HOST),
            port=int(data.get("port", DEFAULT_PORT)),
            pythonVersion=str(data.get("pythonVersion", DEFAULT_PYTHON_VERSION)),
            pipIndexUrl=data.get("pipIndexUrl", DEFAULT_PIP_INDEX_URL),
            hfMirror=data.get("hfMirror", DEFAULT_HF_MIRROR),
            gitRemote=data.get("gitRemote", DEFAULT_GIT_REMOTE),
            huggingfaceRepo=data.get("huggingfaceRepo", DEFAULT_HUGGINGFACE_REPO),
            defaultLang=data.get("defaultLang", "zh"),
            defaultTextSplitMethod=data.get("defaultTextSplitMethod", DEFAULT_TEXT_SPLIT_METHOD),
            inferenceTimeoutMs=int(data.get("inferenceTimeoutMs", DEFAULT_INFERENCE_TIMEOUT_MS)),
            isHalf=bool(data.get("isHalf", DEFAULT_IS_HALF)),
            defaultRefAudio=data.get("defaultRefAudio", "miku-jp"),
        )


@dataclass
class ReferenceAudioEntry:
    name: str
    fileName: str
    promptText: str
    lang: SupportedLang
    createdAt: int
    updatedAt: int


@dataclass
class ReferenceAudioManifest:
    schemaVersion: int = 1
    entries: dict[str, ReferenceAudioEntry] = field(default_factory=dict)


@dataclass
class GenerateByTextOptions:
    text: str
    refAudioName: Optional[str] = None
    refAudioPath: Optional[str] = None
    promptText: Optional[str] = None
    promptLang: Optional[SupportedLang] = None
    textLang: Optional[SupportedLang] = None
    textSplitMethod: Optional[TextSplitMethod] = None
    speedFactor: Optional[float] = None
    topK: Optional[int] = None
    topP: Optional[float] = None
    temperature: Optional[float] = None
    seed: Optional[int] = None
    streaming: Optional[bool] = None
    parallelInfer: Optional[bool] = None
    mediaType: Optional[Literal["wav", "ogg", "aac", "raw"]] = None
    model: Optional[GptSovitsModel] = None
    outputDir: Optional[str] = None
    fileName: Optional[str] = None


@dataclass
class GenerateByTextResult:
    filePath: str
    fileName: str
    modelUsed: GptSovitsModel
    text: str
    inferenceMs: int


@dataclass
class TtsStatus:
    ready: bool
    bootstrapping: bool
    device: Optional[ComputeDevice]
    model: GptSovitsModel
    host: str
    port: int
    pid: Optional[int] = None
    startedAt: Optional[int] = None
    lastError: Optional[str] = None


@dataclass
class BootstrapState:
    phase: str
    message: str
    ready: bool


BootstrapListener = Callable[[BootstrapState], Awaitable[None]] | Callable[[BootstrapState], None]


__all__ = [
    "GptSovitsModel",
    "SupportedLang",
    "TextSplitMethod",
    "ComputeDevice",
    "TtsSettings",
    "ReferenceAudioEntry",
    "ReferenceAudioManifest",
    "GenerateByTextOptions",
    "GenerateByTextResult",
    "TtsStatus",
    "BootstrapState",
    "BootstrapListener",
    "SUPPORTED_LANGS",
    "SUPPORTED_MODELS",
    "SUPPORTED_TEXT_SPLIT_METHODS",
]