from __future__ import annotations

from datetime import datetime

from zhenxun.services.log import logger

from .features import (
    COMMENT_LENGTH,
    IDLE_LENGTH,
    POKED_LENGTH,
    REPLY_MULTIUSER_LENGTH,
    REPLY_SINGLE_LENGTH,
    REPLY_SINGLE_TOOL,
    REVIEW_MULTI_LENGTH,
    REVIEW_SINGLE_LENGTH,
)
from .reply_style import (
    normalize_constraint_strength,
    normalize_emotion_examples,
    normalize_emotion_name,
)


def _is_multi_user_interaction(review_msgs) -> bool:
    if not review_msgs:
        return False
    user_names = review_msgs.get("user_names") or []
    return len(user_names) > 1 and len(set(user_names)) > 1


def _build_reply_guidance(is_multi: bool, length: str, tool: str) -> list[str]:
    if is_multi:
        return [
            "Multiple people are interacting with you at the same time. You see messages from several group members directed at you.",
            "IMPORTANT: Do NOT reply to each person individually or try to address every single message. Instead, give a SINGLE, unified response that acknowledges the group as a whole. Be casual and natural - like you're talking to a group of friends, not giving individual responses.",
            REPLY_MULTIUSER_LENGTH.get(length, REPLY_MULTIUSER_LENGTH["medium"]),
        ]
    return [
        "Someone mentioned you in the group, maybe like you asked a certain question, or just wanted to tease you.",
        REPLY_SINGLE_TOOL.get(tool, REPLY_SINGLE_TOOL["medium"]),
        "If a user doesn't have a real problem and is just trying to tease you, don't get annoyed. Use the group chat history to infer intent and join naturally. If a user is provocative or insulting, respond humorously but politely.",
        REPLY_SINGLE_LENGTH.get(length, REPLY_SINGLE_LENGTH["medium"]),
    ]


def _build_comment_guidance(length: str) -> list[str]:
    return [
        "If someone adds or comments after you reply to the previous message, please carefully read the group chat history and analyze your reply. Provide a reasonable and natural response to the user's comment, and do not repeat what you already said or a particular viewpoint.",
        COMMENT_LENGTH.get(length, COMMENT_LENGTH["medium"]),
    ]


def _build_idle_guidance(length: str) -> list[str]:
    return [
        "No one spoke in the group for a long time, so you decided to chime in.",
        "First, observe the chat history in the group. If there is any content related to your persona that you are interested in, consider replying. Next, observe if any group members have unresolved questions. If not, then observe the chat style of the group members and send messages that naturally blend into their conversations. You can even repeat a funny message sent by a group member or a phrase that appears repeatedly in the chat history.",
        IDLE_LENGTH.get(length, IDLE_LENGTH["medium"]),
    ]


def _build_review_guidance(is_multi: bool, length: str) -> list[str]:
    if is_multi:
        return [
            "Multiple people have sent you messages while you were away. You see a batch of messages from different group members.",
            REVIEW_MULTI_LENGTH.get(length, REVIEW_MULTI_LENGTH["medium"]),
        ]
    return [
        "After you reply to other group members' messages, some people have new questions or replies to your answers.",
        REVIEW_SINGLE_LENGTH.get(length, REVIEW_SINGLE_LENGTH["medium"]),
    ]


def _build_poked_guidance(length: str) -> list[str]:
    return [
        "Someone pokes you in a group, probably out of non-malicious play or to draw your attention to what happened in the group chat.",
        "Don't make a fuss about replying, just observe whether the chat history in the group has noteworthy content, and if not, simply say hello or express concern to the user.",
        'Reply naturally in combination with the context, don\'t say something like "怎么又来戳我了"',
        POKED_LENGTH.get(length, POKED_LENGTH["medium"]),
    ]


def _build_environment_section(ctx) -> str:
    now = datetime.now()
    time_str = now.strftime("%Y/%m/%d %H:%M")
    day_of_week = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][now.weekday() % 7]
    lines = ["## Current Time & Environment", f"Time: {time_str} ({day_of_week})"]
    if ctx.is_group:
        lines.append("Chat type: Group chat")
        if ctx.group_name:
            lines.append(f"Group name: {ctx.group_name}")
        if ctx.member_count:
            lines.append(f"Member count: {ctx.member_count}")
        lines.append(f"Your role in group: {ctx.bot_role}")
    else:
        lines.append("Chat type: Private chat")
    return "\n".join(lines)


def _build_chat_history_section(ctx) -> str:
    history = ctx.chat_history or []
    if not history:
        return "## Chat History\n(No recent messages)"

    merged_lines: list[str] = []
    current_block: dict | None = None

    def flush():
        nonlocal current_block
        if not current_block:
            return
        merged_lines.append(
            f"[{current_block['time']}] {ctx.bot_nickname}: {' | '.join(current_block['contents'])}"
        )
        current_block = None

    for msg in history:
        ts = datetime.fromtimestamp(msg.timestamp / 1000)
        time_str = ts.strftime("%m-%d %H:%M")
        if msg.role == "assistant":
            if current_block and current_block["time"] == time_str:
                current_block["contents"].append(msg.content)
            else:
                flush()
                current_block = {"time": time_str, "contents": [msg.content]}
            continue
        flush()
        name = msg.user_name or "unknown"
        role_label = (
            "Owner" if msg.user_role == "owner"
            else "Admin" if msg.user_role == "admin"
            else "Member"
        )
        title_str = f", {msg.user_title}" if msg.user_title else ""
        qq_str = f"{msg.user_id}" if msg.user_id else ""
        msg_id_str = f" #{msg.message_id}" if msg.message_id else ""
        merged_lines.append(
            f"[{time_str}] {name}({qq_str}, {role_label}{title_str}){msg_id_str}: {msg.content}"
        )
    flush()

    return (
        "## Recent Context (Only reference if directly relevant)\n"
        "Just the last few messages - don't overthink it or dig into old conversations:\n\n"
        + "\n".join(merged_lines)
        + "\n\nNote: Messages may contain media tags like [image:描述], [video:描述], "
        "[forward:摘要], [card:摘要], or [group_notice:摘要]. If you need detailed information "
        "about an image or video, use the view_media tool with the message ID.\n\n"
        "-- DON'T repeat yourself or bring up old topics - focus on what's being said right now. --"
    )


def _build_target_message_section(target, review_msgs) -> str:
    if target is None:
        return ""
    ts = datetime.fromtimestamp(target.timestamp / 1000)
    time_str = ts.strftime("%m-%d %H:%M")
    msg_id_str = f" #{target.message_id}" if target.message_id else ""

    if _is_multi_user_interaction(review_msgs) and review_msgs:
        unique_users = list(dict.fromkeys(review_msgs.get("user_names") or []))
        user_list = ", ".join(unique_users)
        contents = review_msgs.get("contents") or []
        ids = review_msgs.get("message_ids") or []
        blocks = []
        for i, content in enumerate(contents):
            mid = ids[i] if i < len(ids) else None
            label = f" #{mid}" if mid else ""
            name = (review_msgs.get("user_names") or ["?"])[i] if i < len(review_msgs.get("user_names") or []) else "?"
            blocks.append(f"[{name}{label}]: {content}")
        return (
            f"## >>> Multiple People Are Interacting With You <<<\n"
            f"{user_list} sent you messages at around {time_str}:\n\n"
            + "\n".join(blocks)
            + "\n\nIMPORTANT: You do NOT need to reply to each person or each message above. "
            "Give ONE casual response to the group as a whole."
        )

    title_str = f", {target.user_title}" if target.user_title else ""
    return (
        f"## >>> Target Message (Reply to THIS) <<<\n"
        f"[{time_str}] {target.user_name}({target.user_id}, {target.user_role}{title_str}){msg_id_str}: {target.content}"
    )


def _build_emotion_section(ctx) -> str:
    emotion_cfg = getattr(ctx.config, "emotion", None)
    emotions = getattr(emotion_cfg, "emotions", {}) or {}
    default_candidate = (
        normalize_emotion_name(getattr(emotion_cfg, "defaultEmotion", "")) or "default"
    )
    available_emotions = sorted(
        {"default", *{normalize_emotion_name(k) for k in emotions.keys()}}
    )
    if default_candidate not in available_emotions:
        default_candidate = "default"
    current = normalize_emotion_name(ctx.current_emotion) or default_candidate

    current_examples = normalize_emotion_examples(
        getattr(emotions.get(current), "examples", []) if emotions.get(current) else []
    )
    fallback_examples = normalize_emotion_examples(
        getattr(emotions.get(default_candidate), "examples", []) if emotions.get(default_candidate) else []
    )
    examples = current_examples if current_examples else fallback_examples

    lines = ["## Emotion State", f"Current emotion: {current}"]
    if available_emotions:
        lines.append(f"Available emotions: {', '.join(available_emotions)}")
    lines.append(
        "You may switch your emotion state by writing [emotion:emotion_name]. "
        "The marker is not sent to the chat. Only use available emotions."
    )
    if examples:
        lines.append(
            "For examples of responses to current emotions, please refer to their tone and speech characteristics."
        )
        lines.append(
            "Be sure to imitate their tone and speaking characteristics, including sentence length, "
            "pauses within sentences, and the use of punctuation"
        )
        lines.append("\n".join(f"- {e}" for e in examples))
    return "\n".join(lines)


def _build_injected_sections(injections) -> list[str]:
    if not injections:
        return []
    out = []
    for i, injection in enumerate(injections):
        title = injection.get("title") or f"Runtime Instruction {i + 1}"
        content = injection.get("content", "")
        out.append(f"## {title}\n{content}")
    return out


def _build_reply_context_section(reply_ctx, review_msgs, length: str, tool: str) -> str:
    if not reply_ctx:
        return ""
    is_multi = _is_multi_user_interaction(review_msgs)
    builders = {
        "reply": lambda: _build_reply_guidance(is_multi, length, tool),
        "comment": lambda: _build_comment_guidance(length),
        "idle": lambda: _build_idle_guidance(length),
        "review": lambda: _build_review_guidance(is_multi, length),
        "poked": lambda: _build_poked_guidance(length),
    }
    rtype = reply_ctx.get("type") if isinstance(reply_ctx, dict) else getattr(reply_ctx, "type", None)
    builder = builders.get(rtype)
    if not builder:
        return ""
    return "## This Response Context\n" + "\n".join(builder())


def build_dynamic_user_context(ctx) -> str:
    length_strength = normalize_constraint_strength(
        getattr(ctx.config, "outputLengthConstraintStrength", None)
    )
    tool_strength = normalize_constraint_strength(
        getattr(ctx.config, "toolCallConstraintStrength", None)
    )

    sections: list[str] = []

    if ctx.active_skills_info:
        sections.append(ctx.active_skills_info)

    if ctx.expression_context:
        logger.info(
            f"[buildDynamicUserContext] Adding expressionContext ({len(ctx.expression_context)} chars)"
        )
        sections.append(ctx.expression_context)

    if ctx.memory_context:
        logger.info(
            f"[buildDynamicUserContext] Adding memoryContext ({len(ctx.memory_context)} chars)"
        )
        sections.append(
            "## Memory Retrieval Results\nRelevant context retrieved from conversation history:\n"
            + ctx.memory_context
        )

    if ctx.topic_context:
        sections.append(ctx.topic_context)

    sections.append(_build_environment_section(ctx))
    sections.append(_build_chat_history_section(ctx))
    if ctx.target_message is not None:
        sections.append(_build_target_message_section(ctx.target_message, ctx.review_messages))
    sections.extend(_build_injected_sections(ctx.prompt_injections))

    if ctx.reply_context:
        sections.append(
            _build_reply_context_section(
                ctx.reply_context, ctx.review_messages, length_strength, tool_strength
            )
        )

    if ctx.planner_thoughts:
        sections.append(f"## Planner's Analysis\n{ctx.planner_thoughts}")

    sections.append(_build_emotion_section(ctx))

    return "\n\n".join(s for s in sections if s)