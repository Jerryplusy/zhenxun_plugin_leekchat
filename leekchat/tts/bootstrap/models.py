from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from ..constants import G2PW_REPO, HUGGINGFACE_REPO
from ..types import GptSovitsModel
from ..utils.fs import path_exists
from ..utils.log import debug, info
from ..utils.process import run_command

DownloadProgressCb = Callable[[str], Awaitable[None]] | Callable[[str], None]


@dataclass
class ModelSelection:
    local_bert_dir: str
    local_hubert_dir: str
    local_model_dir: str
    local_t2s_path: str
    local_vits_path: str
    remote_t2s_file: str
    remote_vits_file: str
    remote_model_dir: str
    version: GptSovitsModel
    needs_g2pw: bool
    needs_sv_model: bool = False


def _build(opts: dict) -> ModelSelection:
    pretrained = "GPT_SoVITS/pretrained_models"
    return ModelSelection(
        local_bert_dir=f"{pretrained}/chinese-roberta-wwm-ext-large",
        local_hubert_dir=f"{pretrained}/chinese-hubert-base",
        local_model_dir=f"{pretrained}/{opts['remote_model_dir']}",
        local_t2s_path=f"{pretrained}/{opts['remote_t2s_file']}",
        local_vits_path=f"{pretrained}/{opts['remote_vits_file']}",
        remote_t2s_file=opts["remote_t2s_file"],
        remote_vits_file=opts["remote_vits_file"],
        remote_model_dir=opts["remote_model_dir"],
        version=opts["version"],
        needs_g2pw=opts["needs_g2pw"],
        needs_sv_model=opts.get("needs_sv_model", False),
    )


MODEL_PRESETS: dict[GptSovitsModel, ModelSelection] = {
    "v2": _build(
        {
            "remote_model_dir": "gsv-v2final-pretrained",
            "remote_t2s_file": "gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
            "remote_vits_file": "gsv-v2final-pretrained/s2G2333k.pth",
            "needs_g2pw": True,
            "version": "v2",
        }
    ),
    "v2Pro": _build(
        {
            "remote_model_dir": "v2Pro",
            "remote_t2s_file": "s1v3.ckpt",
            "remote_vits_file": "v2Pro/s2Gv2Pro.pth",
            "needs_g2pw": False,
            "needs_sv_model": True,
            "version": "v2Pro",
        }
    ),
    "v2ProPlus": _build(
        {
            "remote_model_dir": "v2Pro",
            "remote_t2s_file": "s1v3.ckpt",
            "remote_vits_file": "v2Pro/s2Gv2ProPlus.pth",
            "needs_g2pw": False,
            "needs_sv_model": True,
            "version": "v2ProPlus",
        }
    ),
    "v4": _build(
        {
            "remote_model_dir": "gsv-v4-pretrained",
            "remote_t2s_file": "s1v3.ckpt",
            "remote_vits_file": "gsv-v4-pretrained/s2Gv4.pth",
            "needs_g2pw": False,
            "version": "v4",
        }
    ),
}


def get_model_selection(model: GptSovitsModel) -> ModelSelection:
    return MODEL_PRESETS[model]


def list_model_selections() -> list[ModelSelection]:
    return list(MODEL_PRESETS.values())


CHINESE_ROBERTA_FILES = ["config.json", "pytorch_model.bin", "tokenizer.json"]
CHINESE_HUBERT_FILES = [
    "config.json",
    "pytorch_model.bin",
    "preprocessor_config.json",
]


def _is_success(code: object) -> bool:
    return code in (0, None)


async def _curl_download(url: str, local_path: str) -> bool:
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    res = await run_command(
        "curl",
        [
            "-L",
            "--fail",
            "--retry",
            "3",
            "--connect-timeout",
            "60",
            "-o",
            local_path,
            url,
        ],
        timeout=1800,
    )
    if _is_success(res["code"]):
        return True
    try:
        Path(local_path).unlink()
    except FileNotFoundError:
        pass
    return False


async def _is_usable_file(local_path: str) -> bool:
    if not await path_exists(local_path):
        return False
    try:
        return Path(local_path).stat().st_size > 0
    except OSError:
        return False


async def _download_dir_files(
    *,
    hf_mirror: str,
    repo: str,
    remote_dir: str,
    local_dir: str,
    files_to_try: list[str],
    label: str,
) -> None:
    Path(local_dir).mkdir(parents=True, exist_ok=True)
    for file_name in files_to_try:
        local_path = os.path.join(local_dir, file_name) if False else str(Path(local_dir) / file_name)
        if await _is_usable_file(local_path):
            continue
        url = f"{hf_mirror}/{repo}/resolve/main/{remote_dir}/{file_name}"
        ok = await _curl_download(url, local_path)
        if ok:
            info(f"下载: {label}/{file_name}")
        else:
            debug(f"跳过 (远端不存在): {file_name}")


async def _download_single_file(
    hf_mirror: str,
    repo: str,
    remote_path: str,
    local_path: str,
    label: str,
) -> None:
    if await _is_usable_file(local_path):
        return
    url = f"{hf_mirror}/{repo}/resolve/main/{remote_path}"
    info(f"下载: {label}")
    ok = await _curl_download(url, local_path)
    if not ok:
        raise RuntimeError(f"下载失败: {url}")


async def ensure_base_pretrained(repo_dir: str, hf_mirror: str) -> None:
    local_root = str(Path(repo_dir) / "GPT_SoVITS" / "pretrained_models")
    await _download_dir_files(
        hf_mirror=hf_mirror,
        repo=HUGGINGFACE_REPO,
        remote_dir="chinese-roberta-wwm-ext-large",
        local_dir=f"{local_root}/chinese-roberta-wwm-ext-large",
        files_to_try=CHINESE_ROBERTA_FILES,
        label="chinese-roberta-wwm-ext-large",
    )
    await _download_dir_files(
        hf_mirror=hf_mirror,
        repo=HUGGINGFACE_REPO,
        remote_dir="chinese-hubert-base",
        local_dir=f"{local_root}/chinese-hubert-base",
        files_to_try=CHINESE_HUBERT_FILES,
        label="chinese-hubert-base",
    )


async def ensure_model_weights(
    repo_dir: str, model: GptSovitsModel, hf_mirror: str
) -> None:
    selection = get_model_selection(model)
    local_root = str(Path(repo_dir) / "GPT_SoVITS" / "pretrained_models")
    debug(f"正在准备 {model} 权重 (目录 {selection.remote_model_dir}/) ...")
    model_dir = f"{local_root}/{selection.remote_model_dir}"
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    if selection.remote_model_dir != ".":
        await _download_dir_files(
            hf_mirror=hf_mirror,
            repo=HUGGINGFACE_REPO,
            remote_dir=selection.remote_model_dir,
            local_dir=model_dir,
            files_to_try=["config.json"],
            label=f"{selection.remote_model_dir}/config.json (optional)",
        )

    await _download_single_file(
        hf_mirror,
        HUGGINGFACE_REPO,
        selection.remote_t2s_file,
        f"{local_root}/{selection.remote_t2s_file}",
        f"{model} t2s: {Path(selection.remote_t2s_file).name}",
    )
    await _download_single_file(
        hf_mirror,
        HUGGINGFACE_REPO,
        selection.remote_vits_file,
        f"{local_root}/{selection.remote_vits_file}",
        f"{model} vits: {Path(selection.remote_vits_file).name}",
    )

    if selection.needs_sv_model:
        sv_local = f"{local_root}/sv/pretrained_eres2netv2w24s4ep4.ckpt"
        await _download_single_file(
            hf_mirror,
            HUGGINGFACE_REPO,
            "sv/pretrained_eres2netv2w24s4ep4.ckpt",
            sv_local,
            "sv/pretrained_eres2netv2w24s4ep4.ckpt",
        )


async def ensure_g2pw_model(repo_dir: str, hf_mirror: str) -> None:
    target = str(Path(repo_dir) / "GPT_SoVITS" / "text")
    marker = f"{target}/G2PWModel"
    if await path_exists(marker):
        info(f"G2PW 模型已存在: {marker}")
        return
    info("正在下载 G2PW 模型 ...")
    Path(target).mkdir(parents=True, exist_ok=True)
    zip_path = f"{target}/G2PWModel.zip"
    await _download_single_file(
        hf_mirror,
        G2PW_REPO,
        "G2PWModel.zip",
        zip_path,
        "G2PWModel.zip",
    )
    info("正在解压 G2PWModel.zip ...")
    ok = await _unzip_archive(zip_path, target)
    if not ok:
        raise RuntimeError(f"解压 G2PWModel.zip 失败: {zip_path}")
    try:
        Path(zip_path).unlink()
    except FileNotFoundError:
        pass


async def _unzip_archive(zip_path: str, dest_dir: str) -> bool:
    res = await run_command(
        "unzip", ["-o", zip_path, "-d", dest_dir], timeout=300
    )
    if _is_success(res["code"]):
        return True
    if not _has_unzip() and not _has_powershell():
        error(f"unzip 失败: {res['stderr'].strip() or res['stdout'].strip()}")
    return False


def _has_unzip() -> bool:
    from ..utils.process import command_exists

    return command_exists("unzip")


def _has_powershell() -> bool:
    import sys

    return sys.platform == "win32"