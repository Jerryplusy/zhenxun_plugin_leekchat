from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.permission import SUPERUSER

from zhenxun.services.log import logger

from ..core.external_skills import DEFAULT_HIDDEN_EXTERNAL_SKILLS
from ..core.skills.registry import get_skill_registry

if TYPE_CHECKING:
    pass


def _wrap(text: str) -> str:
    return text.replace("\n", " ")


def _visible_entries():
    hidden = set(_read_hidden_list())
    return [
        entry
        for entry in get_skill_registry()._entries.values()
        if entry.module not in hidden and entry.name not in hidden
    ]


def _build_help() -> str:
    return (
        "AI 技能管理\n\n"
        "/skills - 显示帮助\n"
        "/skills list - 列出所有技能\n"
        "/skills on <名称|序号> [...] - 启用技能；支持完整名称或"
        "技能列表中的序号，可用空格分隔多个技能\n"
        "/skills off <名称|序号> [...] - 关闭某个技能\n"
        "/skills allon - 启用当前扫描到的全部技能\n"
        "/skills alloff - 不允许任何技能\n"
        "/skills reload - 重新扫描插件并重建技能目录\n"
        "/skills hidden - 查看默认隐藏且禁用的不常用技能\n"
        "/skills hidden add/remove <模块名> [...] - 管理隐藏列表\n"
        "/skills hidden reset - 恢复默认隐藏列表\n\n"
    )


def _build_list_text() -> str:
    registry = get_skill_registry()
    if not registry.scanned:
        return "技能尚未扫描 请先发送 /skills reload"

    allowed = set(_read_current_allowlist())
    is_allowed_mode = bool(allowed)

    entries = sorted(_visible_entries(), key=lambda e: e.name)
    if not entries:
        return "未扫描到技能 当前加载的插件中没有可供 AI 使用的技能"

    lines = []
    for idx, entry in enumerate(entries, 1):
        mark = "x" if (entry.module in allowed or entry.name in allowed) else " "
        if not is_allowed_mode:
            mark = "*"  # all listed but none on allowlist
        lines.append(
            f"[{idx:>3}][{mark}] {entry.module}  -  {_wrap(entry.description)}"
        )

    header = "x = 已启用    * = 已扫描但未加入允许列表\n" + (
        "技能列表为空 上下文无技能\n"
        if not is_allowed_mode
        else "技能列表不为空 上下文存在已勾选的技能\n"
    )
    footer = "\n用法：/skills on <名称|序号> [更多...]    /skills off <...>"
    return header + "\n".join(lines) + footer


def _resolve_targets(args: list[str], for_off: bool = False) -> list[str]:
    registry = get_skill_registry()
    if not registry.scanned:
        return []

    entries = sorted(registry._entries.values(), key=lambda e: e.name)
    by_module = {e.module: e for e in entries}
    by_name = {e.name: e for e in entries}
    by_index = {str(i): e for i, e in enumerate(entries, 1)}

    resolved: list[str] = []
    for raw in args:
        key = raw.strip()
        if not key:
            continue
        entry = by_module.get(key) or by_name.get(key) or by_index.get(key)
        if entry is None:
            logger.warning(f"[leekchat.skills] /skills 未识别: {key!r}")
            continue
        resolved.append(entry.module)
    seen: set[str] = set()
    return [m for m in resolved if not (m in seen or seen.add(m))]


def _read_current_allowlist() -> list[str]:
    from zhenxun.configs.config import Config
    raw = Config.get_config(
        "zhenxun_plugin_leekchat", "allowedExternalSkills", ""
    )
    if not raw:
        return []
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return [str(x).strip() for x in raw if str(x).strip()]


def _write_allowlist(modules: list[str]) -> None:
    from zhenxun.configs.config import Config
    Config.set_config(
        "zhenxun_plugin_leekchat",
        "allowedExternalSkills",
        ",".join(modules),
        auto_save=True,
    )


def _read_hidden_list() -> list[str]:
    from zhenxun.configs.config import Config

    raw = Config.get_config(
        "zhenxun_plugin_leekchat", "hiddenExternalSkills", ""
    )
    if not raw:
        return sorted(DEFAULT_HIDDEN_EXTERNAL_SKILLS)
    if raw == "-":
        return []
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    return [str(x).strip() for x in raw if str(x).strip()]


def _write_hidden_list(modules: list[str]) -> None:
    from zhenxun.configs.config import Config

    normalized = sorted(set(modules))
    Config.set_config(
        "zhenxun_plugin_leekchat",
        "hiddenExternalSkills",
        ",".join(normalized) if normalized else "-",
        auto_save=True,
    )
    try:
        from .. import _plugin_context

        if _plugin_context is not None:
            _plugin_context.config_provider().hiddenExternalSkills = normalized
    except Exception as e:
        logger.warning(f"[leekchat.skills] 同步隐藏列表到运行时失败: {e}")


def _build_hidden_text() -> str:
    hidden = _read_hidden_list()
    lines = "\n".join(f"{i}. {name}" for i, name in enumerate(hidden, 1))
    return (
        f"当前隐藏且默认禁用的技能（{len(hidden)} 个）：\n"
        f"{lines or '（空）'}\n\n"
        "管理命令：\n"
        "/skills hidden add <模块名> [...]\n"
        "/skills hidden remove <模块名> [...]\n"
        "/skills hidden reset"
    )


_skills_handler = on_command(
    "skills", permission=SUPERUSER, priority=5, block=True, aliases={"/skills"}
)


@_skills_handler.handle()
async def _(bot: Bot, event: MessageEvent) -> None:
    raw = event.get_plaintext().strip()
    if raw.startswith("/skills"):
        raw = raw[len("/skills"):].lstrip()
    elif raw.startswith("skills"):
        raw = raw[len("skills"):].lstrip()

    args = raw.split()

    if not args:
        await _skills_handler.finish(_build_help())

    sub = args[0].lower()
    rest = args[1:]

    if sub == "list":
        await _skills_handler.finish(_build_list_text())

    if sub == "help":
        await _skills_handler.finish(_build_help())

    if sub == "hidden":
        if not rest:
            await _skills_handler.finish(_build_hidden_text())
        action = rest[0].lower()
        targets = rest[1:]
        if action == "reset":
            hidden = set(DEFAULT_HIDDEN_EXTERNAL_SKILLS)
        elif action in ("add", "remove"):
            if not targets:
                await _skills_handler.finish(
                    f"用法：/skills hidden {action} <模块名> [...]"
                )
            hidden = set(_read_hidden_list())
            if action == "add":
                hidden.update(targets)
            else:
                hidden.difference_update(targets)
        else:
            await _skills_handler.finish(
                "未知操作"
            )
        _write_hidden_list(sorted(hidden))
        allowed = set(_read_current_allowlist()) - hidden
        _write_allowlist(sorted(allowed))
        await _skills_handler.finish(_build_hidden_text())

    if sub == "reload":
        count = await get_skill_registry().scan()
        await _skills_handler.finish(f"已重新加载技能目录，共扫描到 {count} 个技能")

    if sub == "allon":
        registry = get_skill_registry()
        if not registry.scanned:
            await get_skill_registry().scan()
        modules = sorted(e.module for e in _visible_entries())
        _write_allowlist(modules)
        await _skills_handler.finish(
            f"已启用全部 {len(modules)} 个技能"
        )

    if sub == "alloff":
        _write_allowlist([])
        await _skills_handler.finish(
            "技能列表已清空"
        )

    if sub in ("on", "off"):
        if not rest:
            await _skills_handler.finish(
                f"用法：/skills {sub} <名称|序号> [更多...]\n"
                "请先发送 /skills list 查看技能名称和序号"
            )
        target_modules = _resolve_targets(rest)
        if not target_modules:
            await _skills_handler.finish(
                "输入中没有识别到技能 请先发送 /skills list 查看可用技能"
            )
        current = _read_current_allowlist()
        current_set = set(current)
        if sub == "on":
            new_set = current_set | set(target_modules)
            verb = "已启用"
        else:
            new_set = current_set - set(target_modules)
            verb = "已移除"
        _write_allowlist(sorted(new_set))
        await _skills_handler.finish(
            f"{verb} {len(target_modules)} 个技能，允许列表当前共有 {len(new_set)} 项"
        )

    await _skills_handler.finish(
        f"未知命令：{sub!r} 请发送 /skills 查看帮助"
    )