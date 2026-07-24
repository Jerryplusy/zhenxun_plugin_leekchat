from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zhenxun.services.ai.llm.manager import get_default_model, list_available_models
from zhenxun.services.log import logger


@dataclass
class RoleInstances:
    main: str
    work: str
    vision: str
    models: dict[str, str]
    is_multimodal: bool


def _resolve_model_id(full_name: str | None) -> str:
    if not full_name:
        return ""
    if "/" in full_name:
        return full_name.split("/", 1)[1]
    return full_name


def _find_model_capability(full_name: str | None) -> tuple[str | None, bool]:
    if not full_name:
        return None, False
    for entry in list_available_models():
        if entry.get("full_name", "").lower() == full_name.lower():
            caps = entry.get("capabilities") or {}
            modalities = caps.get("input_modalities") or []
            if not modalities and entry.get("is_multimodal") is not None:
                is_mm = bool(entry.get("is_multimodal"))
            else:
                is_mm = "image" in modalities or "vision" in modalities
            return full_name, is_mm
    return full_name, False


def resolve_role_instances(
    main_model: str,
    working_model: str,
    multimodal_working_model: str,
) -> RoleInstances | None:
    """从 zhenxun AI.PROVIDERS 解析 main/working/vision 三个角色。"""
    default = get_default_model("chat") or ""

    main = main_model or default
    work = working_model or main
    vision = multimodal_working_model or work

    if not main:
        logger.error("未配置主模型，请在 zhenxun AI 设置中配置")
        return None

    _, main_mm = _find_model_capability(main)
    if main_mm:
        is_multimodal = True
    else:
        _, vision_mm = _find_model_capability(vision)
        is_multimodal = vision_mm

    return RoleInstances(
        main=main,
        work=work,
        vision=vision,
        models={
            "main": _resolve_model_id(main),
            "working": _resolve_model_id(work),
            "vision": _resolve_model_id(vision),
        },
        is_multimodal=is_multimodal,
    )


def find_model_full_id(short_id: str) -> str | None:
    if "/" in short_id:
        return short_id
    for entry in list_available_models():
        if entry.get("model_name") == short_id:
            return entry.get("full_name")
    return None


def list_models_dict() -> list[dict[str, Any]]:
    return list_available_models()