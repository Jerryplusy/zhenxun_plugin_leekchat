from __future__ import annotations

from nonebot.plugin import PluginMetadata

from zhenxun.configs.utils import (
    Command,
    PluginCdBlock,
    PluginExtraData,
    PluginSetting,
    RegisterConfig,
)


__plugin_meta__ = PluginMetadata(
    name="leekchat",
    description="基于 zhenxun AI 服务的多模型 AI 聊天插件",
    usage=(
        "@bot、使用昵称触发或引用都可以哦"
    ).strip(),
    extra=PluginExtraData(
        author="leekchat team",
        version="1.0.0",
        menu_type="聊天功能",
        configs=[
            RegisterConfig(
                module="zhenxun_plugin_leekchat",
                key="MAIN_MODEL",
                value="",
                help="主模型，格式 ProviderName/ModelName（如 OpenAI/gpt-4o）",
                default_value="",
                type=str,
            ),
            RegisterConfig(
                module="zhenxun_plugin_leekchat",
                key="WORKING_MODEL",
                value="",
                help="工作模型（多模态识别、规划、表情包选择）",
                default_value="",
                type=str,
            ),
            RegisterConfig(
                module="zhenxun_plugin_leekchat",
                key="VISION_MODEL",
                value="",
                help="视觉工作模型",
                default_value="",
                type=str,
            ),
            RegisterConfig(
                module="zhenxun_plugin_leekchat",
                key="BASE",
                value="{}",
                help="基础配置 JSON",
                default_value="{}",
                type=str,
            ),
            RegisterConfig(
                module="zhenxun_plugin_leekchat",
                key="SETTINGS",
                value="{}",
                help="设置项配置 JSON",
                default_value="{}",
                type=str,
            ),
            RegisterConfig(
                module="zhenxun_plugin_leekchat",
                key="PERSONALIZATION",
                value="{}",
                help="个性化配置 JSON（人设、情感、风格）",
                default_value="{}",
                type=str,
            ),
            RegisterConfig(
                module="zhenxun_plugin_leekchat",
                key="GROUPS",
                value="{}",
                help="群覆盖配置 JSON",
                default_value="{}",
                type=str,
            ),
        ],
        limits=[PluginCdBlock(cd=5, result="每5秒才能发一条哦~")],
        commands=[
            Command(command="重置会话", description="重置当前会话的 AI 消息"),
        ],
        setting=PluginSetting(level=5),
    ).to_dict(),
)