from __future__ import annotations

from pathlib import Path

from ..utils.paths import LEEKCHAT_DATA_ROOT

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = LEEKCHAT_DATA_ROOT / "tts"
REPO_DIRNAME = "GPT-SoVITS"
VENV_DIRNAME = "venv"
REFERENCE_AUDIO_DIRNAME = "reference-audio"
PRETRAINED_DIRNAME = "GPT_SoVITS/pretrained_models"
G2PW_TARGET_DIRNAME = "GPT_SoVITS/text/G2PWModel"
RUNTIME_LOG_FILENAME = "runtime.log"
TEMP_AUDIO_DIRNAME = "temp"

DEFAULT_REFERENCE_AUDIO_NAME = "miku-jp"


class BundledReferenceAudio:
    __slots__ = ("name", "filename", "lang", "prompt_text")

    def __init__(self, name: str, filename: str, lang: str, prompt_text: str) -> None:
        self.name = name
        self.filename = filename
        self.lang = lang
        self.prompt_text = prompt_text


BUNDLED_REFERENCE_AUDIOS: list[BundledReferenceAudio] = [
    BundledReferenceAudio(
        name="miku-jp",
        filename="miku-jp.mp3",
        lang="ja",
        prompt_text=(
            "みなさん、こんばんは！今日も元気いっぱい歌っていきますよ！"
            "新しい曲もたくさん練習したので、楽しみにしていてください。"
            "私の歌声で、みんなの心に届けられますように。"
            "それじゃあ、始めましょう！"
        ),
    ),
    BundledReferenceAudio(
        name="miku-cn",
        filename="miku-cn.mp3",
        lang="zh",
        prompt_text=(
            "语音合成是通过机械的、电子的方法产生人造语音的技术。"
            "TTS技术（又称文语转换技术）隶属于语音合成，"
            "它是将计算机自己产生的、或外部输入的文字信息"
            "转变为可以听得懂的、流利的汉语口语输出的技术。"
        ),
    ),
    BundledReferenceAudio(
        name="khn-jp",
        filename="khn-jp.wav",
        lang="ja",
        prompt_text=(
            "週末？　えっと、土曜は別の学校の人と約束があるけど、"
            "日曜は何もないよ"
        ),
    ),
]


GPT_SOVITS_REPO_URL = (
    "https://gh-proxy.com/https://github.com/RVC-Boss/GPT-SoVITS.git"
)
HUGGINGFACE_REPO = "lj1995/GPT-SoVITS"
G2PW_REPO = "XXXXRT/GPT-SoVITS-Pretrained"

DEFAULT_GIT_REMOTE = GPT_SOVITS_REPO_URL
DEFAULT_PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
DEFAULT_HF_MIRROR = "https://hf-mirror.com"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9881
DEFAULT_PYTHON_VERSION = "3.10"
DEFAULT_TEXT_SPLIT_METHOD = "cut5"
DEFAULT_INFERENCE_TIMEOUT_MS = 120_000
DEFAULT_IS_HALF = True
DEFAULT_HUGGINGFACE_REPO = HUGGINGFACE_REPO

SUPPORTED_MODELS = ("v2", "v2Pro", "v2ProPlus", "v4")
SUPPORTED_LANGS = ("zh", "en", "ja", "ko", "yue")
SUPPORTED_TEXT_SPLIT_METHODS = (
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
)

REQUIRED_DISK_GB = 8
MIN_RAM_GB = 8
BOOTSTRAP_READY_TIMEOUT_MS = 600_000
RUNTIME_STARTUP_TIMEOUT_MS = 120_000

VENV_PY_MIN = (3, 10)
VENV_PY_MAX_EXCLUSIVE = (3, 13)
SUPPORTED_PY_VERSIONS = ("3.10", "3.11", "3.12")