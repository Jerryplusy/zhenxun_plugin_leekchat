from __future__ import annotations

from typing import Any

from nonebot.plugin import PluginMetadata

from zhenxun.configs.utils import (
    Command,
    PluginCdBlock,
    PluginExtraData,
    PluginSetting,
    RegisterConfig,
)

from .configs import (
    BASE_CONFIG,
    PERSONALIZATION_CONFIG,
    SETTINGS_CONFIG,
    flatten_dict,
    help_for,
)


_MODULE = "zhenxun_plugin_leekchat"

_NEWLINE_LIST_LEAVES = {"examples", "multipleStyles"}


def _make_config(key: str, value: Any) -> RegisterConfig:
    """从扁平 (key, value) 生成 RegisterConfig。help 用中文描述"""
    leaf = key.rsplit("_", 1)[-1]
    help_text = help_for(key)
    if isinstance(value, list):
        if leaf in _NEWLINE_LIST_LEAVES:
            joined = "\n".join(str(x) for x in value)
        else:
            joined = ",".join(str(x) for x in value)
        return RegisterConfig(
            module=_MODULE,
            key=key,
            value=joined,
            help=help_text,
            default_value=joined,
            type=str,
        )
    return RegisterConfig(
        module=_MODULE,
        key=key,
        value=value,
        help=help_text,
        default_value=value,
        type=type(value) if value is not None else str,
    )


_all_configs: list[RegisterConfig] = [
    RegisterConfig(
        module=_MODULE,
        key="MAIN_MODEL",
        value="",
        help="主模型，格式 ProviderName/ModelName（如 OpenAI/gpt-4o）",
        default_value="",
        type=str,
    ),
    RegisterConfig(
        module=_MODULE,
        key="WORKING_MODEL",
        value="",
        help="工作模型（多模态识别、规划、表情包选择）",
        default_value="",
        type=str,
    ),
    RegisterConfig(
        module=_MODULE,
        key="VISION_MODEL",
        value="",
        help="视觉工作模型",
        default_value="",
        type=str,
    ),
    *[_make_config(k, v) for k, v in flatten_dict("BASE", BASE_CONFIG)],
    *[_make_config(k, v) for k, v in flatten_dict("SETTINGS", SETTINGS_CONFIG)],
    *[_make_config(k, v) for k, v in flatten_dict("PERSONALIZATION", PERSONALIZATION_CONFIG)],
]


__plugin_meta__ = PluginMetadata(
    name="leekchat",
    description="基于 zhenxun AI 服务的多模型 AI 聊天插件",
    usage=("@bot、使用昵称触发或引用都可以哦").strip(),
    extra=PluginExtraData(
        author="leekchat team",
        version="1.0.0",
        menu_type="聊天功能",
        configs=_all_configs,
        limits=[PluginCdBlock(cd=5, result="每5秒才能发一条哦~")],
        commands=[
            Command(command="重置会话", description="重置当前会话的 AI 消息"),
        ],
        setting=PluginSetting(level=5),
    ).to_dict(),
)