from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strength:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    VALUES = ("low", "medium", "high")


StrengthT = Literal["low", "medium", "high"]


class SearxngConfig(BaseModel):
    enabled: bool = True
    baseUrl: str = "https://search.crystelf.top/"
    timeoutMs: int = 8000
    defaultLimit: int = 5
    maxLimit: int = 8
    maxSearchCount: int = 4


class WebReaderConfig(BaseModel):
    enabled: bool = True
    useWorkingModel: bool = True
    timeoutMs: int = 10_000
    maxHtmlBytes: int = 1_500_000
    maxExtractedChars: int = 12_000
    browserTimeoutMs: int = 15_000
    allowedContentTypes: list[str] = Field(
        default_factory=lambda: ["text/html", "application/xhtml+xml", "text/plain"]
    )


class AudioConfig(BaseModel):
    enabled: bool = True
    baseUrl: str = "http://localhost:3939"
    apiKey: str = "fufu"
    timeoutMs: int = 40_000


class AIRequestLimitConfig(BaseModel):
    userRpm: int = 3
    groupRpm: int = 6
    windowMs: int = 60_000


class DynamicDelayConfig(BaseModel):
    enabled: bool = True
    interactionWindowMs: int = 60_000
    baseDelayMs: int = 30_000
    maxDelayMs: int = 300_000


class EmotionEntryConfig(BaseModel):
    examples: list[str] = Field(default_factory=list)


class EmotionConfig(BaseModel):
    defaultEmotion: str = "default"
    updateIntervalMs: int = 60 * 60_000
    emotions: dict[str, EmotionEntryConfig] = Field(default_factory=dict)


class ReplyStyleConfig(BaseModel):
    baseStyle: str = ""
    multipleStyles: list[str] = Field(default_factory=list)
    multipleProbability: float = 0.2


class MemoryConfig(BaseModel):
    enabled: bool = True
    groupHistoryLimit: int = 800
    userHistoryLimit: int = 100


class TopicConfig(BaseModel):
    enabled: bool = True
    windowHours: int = 5
    historyWindowCount: int = 3


class PlannerConfig(BaseModel):
    enabled: bool = True
    idleThresholdMs: int = 30 * 60_000
    idleMessageCount: int = 100
    idleCheckBotIds: list[int] = Field(default_factory=list)


class EmojiConfig(BaseModel):
    enabled: bool = True
    characters: list[str] = Field(default_factory=list)
    stickers: list[str] = Field(default_factory=list)


class ExpressionConfig(BaseModel):
    enabled: bool = True
    learnAfterMessages: int = 100
    sampleSize: int = 3


class RetentionConfig(BaseModel):
    enabled: bool = True
    messageRetentionMs: int = 30 * 24 * 60 * 60 * 1000
    topicRetentionMs: int = 90 * 24 * 60 * 60 * 1000
    mediaSummaryRetentionMs: int = 30 * 24 * 60 * 60 * 1000
    imageRetentionMs: int = 60 * 24 * 60 * 60 * 1000
    expressionKeepPerUser: int = 6
    cleanupIntervalMs: int = 60 * 60 * 1000


class LeekchatConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    maxContextTokens: int = 128
    temperature: float = 0.8
    historyCount: int = 100
    maxIterations: int = 20
    enableMediaRecognition: bool = True

    searxng: SearxngConfig = Field(default_factory=SearxngConfig)
    webReader: WebReaderConfig = Field(default_factory=WebReaderConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    blacklistGroups: list[int] = Field(default_factory=list)
    whitelistGroups: list[int] = Field(default_factory=list)
    mediaAnalysisBlacklistUsers: list[int] = Field(default_factory=list)
    maxSessions: int = 100
    enableExternalSkills: bool = True
    allowedExternalSkills: list[str] = Field(default_factory=list)
    stream: bool = True
    enableTypingDelay: bool = True
    typingDelayMaxTotalMs: int = 10_000
    enableMarkdownScreenshot: bool = True
    debug: bool = False
    outputLengthConstraintStrength: StrengthT = "medium"
    toolCallConstraintStrength: StrengthT = "medium"
    emojiUsageConstraintStrength: StrengthT = "medium"
    audioUsageConstraintStrength: StrengthT = "medium"
    markdownUsageConstraintStrength: StrengthT = "medium"
    groupStructuredHistoryTtlMs: int = 10 * 60_000
    nicknames: list[str] = Field(default_factory=lambda: ["miku", "未来", "初音"])
    cooldownAfterReplyMs: int = 20_000
    aiRequestLimits: AIRequestLimitConfig = Field(default_factory=AIRequestLimitConfig)
    dynamicDelay: DynamicDelayConfig = Field(default_factory=DynamicDelayConfig)

    persona: str = ""
    emotion: EmotionConfig = Field(default_factory=EmotionConfig)
    replyStyle: ReplyStyleConfig = Field(default_factory=ReplyStyleConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    topic: TopicConfig = Field(default_factory=TopicConfig)
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    emoji: EmojiConfig = Field(default_factory=EmojiConfig)
    expression: ExpressionConfig = Field(default_factory=ExpressionConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)

    mainModel: str = ""
    workingModel: str = ""
    multimodalWorkingModel: str = ""
    isMultimodal: bool = True


BASE_CONFIG: dict = {
    "maxContextTokens": 128,
    "temperature": 0.8,
    "historyCount": 100,
    "maxIterations": 20,
    "enableMediaRecognition": True,
}


SETTINGS_CONFIG: dict = {
    "searxng": SearxngConfig().model_dump(),
    "webReader": WebReaderConfig().model_dump(),
    "audio": AudioConfig().model_dump(),
    "blacklistGroups": [],
    "whitelistGroups": [],
    "mediaAnalysisBlacklistUsers": [],
    "maxSessions": 100,
    "enableExternalSkills": True,
    "allowedExternalSkills": [],
    "stream": True,
    "enableTypingDelay": True,
    "typingDelayMaxTotalMs": 10_000,
    "enableMarkdownScreenshot": True,
    "debug": False,
    "outputLengthConstraintStrength": "medium",
    "toolCallConstraintStrength": "medium",
    "emojiUsageConstraintStrength": "medium",
    "audioUsageConstraintStrength": "medium",
    "markdownUsageConstraintStrength": "medium",
    "groupStructuredHistoryTtlMs": 10 * 60_000,
    "nicknames": ["miku", "未来", "初音"],
    "cooldownAfterReplyMs": 20_000,
    "aiRequestLimits": AIRequestLimitConfig().model_dump(),
    "dynamicDelay": DynamicDelayConfig().model_dump(),
}