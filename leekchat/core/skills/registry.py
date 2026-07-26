from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import nonebot

from zhenxun.services.log import logger

from ..tools.permissions import ToolPermission


@dataclass
class SkillEntry:
    module: str
    """PluginInfo.module，技能唯一键"""
    name: str
    """metadata.name 显示名"""
    description: str
    usage: str
    commands: list[dict] = field(default_factory=list)
    """[{command, description}] 来自 PluginExtraData.commands"""
    kind: str = "command"
    """smart（有 smart_tools 直调函数）| command（模拟命令消息触发）"""
    smart_tools: list = field(default_factory=list)
    """AICallableTag 列表（kind=smart 时非空，func 均可调用）"""
    min_permission: ToolPermission = ToolPermission.MEMBER
    menu_type: str = ""


def _map_permission(plugin_type) -> ToolPermission:
    from zhenxun.utils.enum import PluginType

    if plugin_type == PluginType.SUPERUSER:
        return ToolPermission.SUPERUSER
    if plugin_type in (PluginType.ADMIN, PluginType.SUPER_AND_ADMIN):
        return ToolPermission.ADMIN
    return ToolPermission.MEMBER


class SkillRegistry:
    """扫描已加载的 nonebot/zhenxun 插件，生成 AI 技能目录

    数据来源：PluginInfo 表（运行时开关/类型） ⋈ nonebot 插件 metadata
    （name/description/usage + PluginExtraData 的 commands/smart_tools）。
    """

    _SELF_MODULES = {"zhenxun_plugin_leekchat", "leekchat"}

    def __init__(self) -> None:
        self._entries: dict[str, SkillEntry] = {}
        self._name_index: dict[str, str] = {}
        self._scanned = False

    @property
    def scanned(self) -> bool:
        return self._scanned

    async def scan(self) -> int:
        from zhenxun.configs.utils import PluginExtraData
        from zhenxun.models.plugin_info import PluginInfo
        from zhenxun.utils.enum import PluginType

        entries: dict[str, SkillEntry] = {}
        name_index: dict[str, str] = {}
        try:
            plugins = await PluginInfo.get_plugins(
                load_status=True,
                status=True,
                is_show=True,
                plugin_type__in=[
                    PluginType.NORMAL,
                    PluginType.ADMIN,
                    PluginType.SUPERUSER,
                    PluginType.SUPER_AND_ADMIN,
                ],
            )
        except Exception as e:
            logger.error(f"[leekchat.skills] 查询 PluginInfo 失败: {e}", e=e)
            return 0

        for p in plugins:
            if p.module in self._SELF_MODULES:
                continue
            entry = self._build_entry(p, PluginExtraData)
            if entry is None:
                continue
            entries[entry.module] = entry
            name_index[entry.name] = entry.module

        self._entries = entries
        self._name_index = name_index
        self._scanned = True
        smart_count = sum(1 for e in entries.values() if e.kind == "smart")
        logger.info(
            f"[leekchat.skills] 技能扫描完成: {len(entries)} 个"
            f"（smart 直调 {smart_count}，命令型 {len(entries) - smart_count}）"
        )
        return len(entries)

    def _build_entry(self, plugin_info, extra_cls) -> SkillEntry | None:
        nb_plugin = nonebot.get_plugin_by_module_name(plugin_info.module_path)
        meta = getattr(nb_plugin, "metadata", None) if nb_plugin else None
        if meta is None:
            return None

        extra: Any = None
        raw_extra = getattr(meta, "extra", None)
        if isinstance(raw_extra, dict) and raw_extra:
            try:
                extra = extra_cls(**raw_extra)
            except Exception:
                extra = None

        smart_tools = []
        if extra is not None and extra.smart_tools:
            smart_tools = [t for t in extra.smart_tools if callable(t.func)]

        commands: list[dict] = []
        if extra is not None:
            commands = [
                {"command": c.command, "description": c.description or ""}
                for c in (extra.commands or [])
            ]

        usage = (meta.usage or "").strip()
        kind = "smart" if smart_tools else "command"
        if kind == "command" and not usage and not commands:
            return None

        description = (meta.description or "").strip() or plugin_info.name
        return SkillEntry(
            module=plugin_info.module,
            name=(meta.name or plugin_info.name).strip(),
            description=description,
            usage=usage,
            commands=commands,
            kind=kind,
            smart_tools=smart_tools,
            min_permission=_map_permission(plugin_info.plugin_type),
            menu_type=plugin_info.menu_type or "",
        )

    def resolve(self, skill_name: str) -> SkillEntry | None:
        """按 module 或显示名定位技能。"""
        key = (skill_name or "").strip()
        if not key:
            return None
        if key in self._entries:
            return self._entries[key]
        module = self._name_index.get(key)
        return self._entries.get(module) if module else None

    def catalog(
        self,
        user_permission: ToolPermission = ToolPermission.MEMBER,
        allowed_names: set[str] | None = None,
    ) -> list[dict]:
        """技能目录（供 system prompt 展示），按权限与白名单过滤。"""
        result: list[dict] = []
        for entry in self._entries.values():
            if user_permission < entry.min_permission:
                continue
            if allowed_names and not (
                entry.module in allowed_names or entry.name in allowed_names
            ):
                continue
            result.append(
                {"name": entry.module, "description": f"{entry.name}：{entry.description}"}
            )
        result.sort(key=lambda x: x["name"])
        return result


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
