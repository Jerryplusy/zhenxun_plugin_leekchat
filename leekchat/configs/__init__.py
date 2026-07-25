from __future__ import annotations

from typing import Any

from .base import (
    BASE_CONFIG,
    SETTINGS_CONFIG,
    AudioConfig,
    AIRequestLimitConfig,
    DynamicDelayConfig,
    EmotionConfig,
    EmojiConfig,
    ExpressionConfig,
    LeekchatConfig,
    MemoryConfig,
    PlannerConfig,
    ReplyStyleConfig,
    RetentionConfig,
    SearxngConfig,
    TopicConfig,
    WebReaderConfig,
)
from .personalization import PERSONALIZATION_CONFIG


SKIP_KEYS: set[str] = set()


_HELP_MAP: dict[str, str] = {
    # BASE
    "maxContextTokens": "单次请求最大上下文 token 数",
    "temperature": "生成温度（0.0-2.0，越高越发散）",
    "historyCount": "保留的历史消息条数",
    "maxIterations": "单次回复最大工具调用轮次",
    "enableMediaRecognition": "是否启用媒体识别",
    # SETTINGS 顶层
    "blacklistGroups": "黑名单群组 ID（逗号分隔）",
    "whitelistGroups": "白名单群组 ID（逗号分隔，留空不限制）",
    "mediaAnalysisBlacklistUsers": "媒体分析黑名单用户 ID（逗号分隔）",
    "maxSessions": "最大并发会话数",
    "enableExternalSkills": "是否启用外部技能",
    "allowedExternalSkills": "允许的外部技能名称（逗号分隔，留空全部允许）",
    "stream": "是否启用流式输出",
    "enableTypingDelay": "是否启用打字延迟模拟",
    "typingDelayMaxTotalMs": "打字延迟最大总时长（毫秒）",
    "enableMarkdownScreenshot": "Markdown 长消息是否自动截图",
    "debug": "是否启用调试模式",
    "outputLengthConstraintStrength": "输出长度约束强度（low/medium/high）",
    "toolCallConstraintStrength": "工具调用约束强度（low/medium/high）",
    "emojiUsageConstraintStrength": "表情包使用约束强度（low/medium/high）",
    "audioUsageConstraintStrength": "音频使用约束强度（low/medium/high）",
    "markdownUsageConstraintStrength": "Markdown 使用约束强度（low/medium/high）",
    "groupStructuredHistoryTtlMs": "群结构化历史 TTL（毫秒）",
    "nicknames": "机器人昵称（逗号分隔）",
    "cooldownAfterReplyMs": "回复后冷却时间（毫秒）",
    # SETTINGS 子模块通用字段
    "enabled": "是否启用",
    "baseUrl": "服务地址",
    "apiKey": "API Key",
    "timeoutMs": "超时时间（毫秒）",
    "useWorkingModel": "是否使用工作模型",
    # searxng
    "defaultLimit": "默认返回结果数",
    "maxLimit": "最大返回结果数",
    "maxSearchCount": "单次任务最大搜索次数",
    # webReader
    "maxHtmlBytes": "最大 HTML 字节数",
    "maxExtractedChars": "最大提取字符数",
    "browserTimeoutMs": "浏览器渲染超时（毫秒）",
    "allowedContentTypes": "允许的 Content-Type（逗号分隔）",
    # aiRequestLimits
    "userRpm": "单用户每分钟最大请求数",
    "groupRpm": "单群每分钟最大请求数",
    "windowMs": "限流统计窗口（毫秒）",
    # dynamicDelay
    "interactionWindowMs": "互动统计窗口（毫秒）",
    "baseDelayMs": "基础延迟（毫秒）",
    "maxDelayMs": "最大延迟（毫秒）",
    # PERSONALIZATION
    "persona": "人设提示词",
    "defaultEmotion": "默认情感 key",
    "updateIntervalMs": "情感更新间隔（毫秒）",
    "examples": "示例文案（每行一条）",
    "baseStyle": "基础回复风格",
    "multipleStyles": "回复多风格列表（每行一条）",
    "multipleProbability": "多风格触发概率（0.0-1.0）",
    # memory
    "groupHistoryLimit": "群历史消息保留条数",
    "userHistoryLimit": "单用户历史消息保留条数",
    # topic
    "windowHours": "话题窗口时长（小时）",
    "historyWindowCount": "历史话题窗口数量",
    # planner
    "idleThresholdMs": "空闲判定阈值（毫秒）",
    "idleMessageCount": "空闲判定消息数",
    "idleCheckBotIds": "检查空闲的机器人 ID（逗号分隔）",
    # emoji
    "characters": "角色表情包关键词（逗号分隔）",
    "stickers": "表情包文件名（逗号分隔）",
    # expression
    "learnAfterMessages": "每多少条消息学习一次表达",
    "sampleSize": "每次学习的样本数",
    # retention
    "messageRetentionMs": "消息保留时长（毫秒，默认30天）",
    "topicRetentionMs": "话题保留时长（毫秒，默认90天）",
    "mediaSummaryRetentionMs": "媒体摘要保留时长（毫秒，默认30天）",
    "imageRetentionMs": "图片保留时长（毫秒，默认60天）",
    "expressionKeepPerUser": "每用户保留表达数",
    "cleanupIntervalMs": "自动清理间隔（毫秒）",
}


def help_for(flat_key: str) -> str:
    """根据扁平 key 返回中文 help。先查完整 key，再查叶子名，最后回退字段名"""
    if flat_key in _HELP_MAP:
        return _HELP_MAP[flat_key]
    leaf = flat_key.rsplit("_", 1)[-1]
    return _HELP_MAP.get(leaf, leaf)


def flatten_dict(prefix: str, nested: dict[str, Any], skip_keys: set[str] = SKIP_KEYS):
    """扁平化嵌套 dict，保留 camelCase key
    """
    result: list[tuple[str, Any]] = []
    for k, v in nested.items():
        if k in skip_keys:
            continue
        key = f"{prefix}_{k}"
        if isinstance(v, dict):
            result.extend(flatten_dict(key, v, skip_keys))
        else:
            result.append((key, v))
    return result


__all__ = [
    "AIRequestLimitConfig",
    "AudioConfig",
    "BASE_CONFIG",
    "DynamicDelayConfig",
    "EmotionConfig",
    "EmojiConfig",
    "ExpressionConfig",
    "LeekchatConfig",
    "MemoryConfig",
    "PERSONALIZATION_CONFIG",
    "PlannerConfig",
    "ReplyStyleConfig",
    "RetentionConfig",
    "SKIP_KEYS",
    "SETTINGS_CONFIG",
    "SearxngConfig",
    "TopicConfig",
    "WebReaderConfig",
    "flatten_dict",
    "help_for",
]