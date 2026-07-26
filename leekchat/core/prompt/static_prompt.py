from __future__ import annotations

from .features import (
    AUDIO_MODE_LINE,
    EMOJI_MODE_LINE,
    MARKDOWN_MODE_LINE,
    TOOL_INTENSITY_BLOCK,
)
from .reply_style import normalize_constraint_strength


def build_persona_section(persona: str | None) -> str:
    lines = ["## Persona"]
    if persona:
        lines.append(persona)
    return "\n".join(lines)


def _append_emoji_section(lines: list[str], config, emoji_strength: str) -> None:
    emoji_cfg = getattr(config, "emoji", None)
    if not emoji_cfg or not getattr(emoji_cfg, "enabled", False):
        return
    lines.append(f"""
### Optional Sticker / Emoji Format
- You MAY optionally request one matching sticker by writing exactly [] on its own line
{EMOJI_MODE_LINE.get(emoji_strength, EMOJI_MODE_LINE["medium"])}
- Never put an emotion, label, character, or any other text inside the brackets
- Output at most one [] block in a turn
- A separate sticker selection agent will read the current conversation and choose the actual sticker""")


def _append_external_skills_section(lines: list[str], config, allowed_skills) -> None:
    if not getattr(config, "enableExternalSkills", False):
        return

    builtin_descs: list[str] = []
    if getattr(getattr(config, "searxng", None), "enabled", False):
        builtin_descs.append("- web_search: search the web")
    if getattr(getattr(config, "webReader", None), "enabled", False):
        builtin_descs.append("- web_read_page: fetch a web page")

    plugin_list = (
        "\n".join(f"- {s['name']}: {s['description']}" for s in allowed_skills)
        if allowed_skills
        else ""
    )
    builtin_list = "\n".join(builtin_descs)
    combined = (plugin_list + "\n" + builtin_list) if plugin_list else builtin_list
    if combined:
        lines.append(f"""
### External Skills
Use the `load_skill` tool to load a skill (valid 1h). Read each tool's description for usage and parameters before calling it.
Allowed skills:
{combined}""")


def build_response_format_section(
    config,
    tool_strength: str,
    emoji_strength: str,
    audio_strength: str,
    markdown_strength: str,
    allowed_skills: list | None = None,
) -> str:
    lines = ["## Response Format"]
    lines.append("""Your text response IS your reply to the chat. It will be sent directly as a message.
- **IMPORTANT: Output ONLY your final reply text. Do NOT include your thinking process, reasoning, analysis, or internal thoughts.**
- Do NOT prefix your response with phrases like "Let me think", "I should", "I need to", "Based on", "Looking at", etc.
- Do NOT explain what you're doing or why. Just say what you want to say directly.
- **MULTIPLE MESSAGES (CRITICAL!): Each line (separated by Enter/Return) will be sent as a SEPARATE message.**
  - If you want to send multiple messages, just press Enter and write the next line
  - Each line = one message sent to the chat
  - **If your reply has multiple sentences or different points, ALWAYS use real line breaks to separate them**
  - NEVER use "\\\\" or literal "\\\\n" to simulate a new line
- **MESSAGE ORDER MATTERS**: messages are sent top-to-bottom, one line at a time.
- For action markers like [] or [audio:...], put them on their own line when they are meant to be a separate action.

- **SPECIAL ACTIONS in your text (auto-parsed and removed from message):**
  - Use [at:123456] in your text to @ someone (123456 is the QQ number)
  - Use [poke:123456] in your text to poke someone. IMPORTANT: when you plan to poke a user, DON't emphasize words like "戳你一下 or 戳回去" to describe your actions
  - Use [reply:123456] at the START of a line to quote-reply that message (123456 is message_id)
  - **You can use MULTIPLE [reply:xxx] markers in different lines to quote multiple messages!**
  - These markers will be automatically parsed and removed from your sent message""")

    audio_cfg = getattr(config, "audio", None)
    if audio_cfg and getattr(audio_cfg, "enabled", False) and getattr(audio_cfg, "baseUrl", "").strip():
        lines.append(f"""
### Optional Voice Message Format
- You MAY optionally send one voice message by writing [audio:content]
- Audio is OPTIONAL. Do NOT use it in every reply
The voice message function sends plain text and cannot be used for singing. If a user needs you to sing, other skills should be considered first.
- Put [audio:...] on its own line when you want it sent as a separate message in sequence
- Example: "[audio:おはようー]"
{AUDIO_MODE_LINE.get(audio_strength, AUDIO_MODE_LINE["medium"])}""")

    if getattr(config, "enableMarkdownScreenshot", False):
        lines.append(f"""
### Optional Markdown Screenshot Format
- You MAY optionally send one rendered Markdown screenshot by wrapping content with exact tags: <MARKDOWN> ... </MARKDOWN>
- Put the Markdown block on its own message whenever possible.
- It is forbidden to use Markdown syntax or formulas in plain text; they must be rendered using <MARKDOWN> blocks.
{MARKDOWN_MODE_LINE.get(markdown_strength, MARKDOWN_MODE_LINE["medium"])}
- Inside <MARKDOWN>...</MARKDOWN>, there is NO length limit. If the user needs detail, explain clearly and thoroughly instead of over-compressing.""")

    lines.append(TOOL_INTENSITY_BLOCK.get(tool_strength, TOOL_INTENSITY_BLOCK["medium"]))

    lines.append("""
### Tool Calling Format
- When you decide to use a tool, you MUST use the structured tool_calls mechanism provided by the API
- Do NOT output tool calls, tool names, or tool arguments in your reply text under any circumstances
- Do NOT use XML, JSON, or any text format to describe tool calls - only use the API's tool_calls field
- Each tool's description contains its own usage guidance; read those before calling a tool. If a tool's description says "use only when X" or "do not call for every question", respect that.
- web_search and web_read_page are limited per conversation; do not retry excessively""")

    _append_emoji_section(lines, config, emoji_strength)
    _append_external_skills_section(lines, config, allowed_skills or [])

    return "\n".join(lines)


def build_static_system_prompt(
    config,
    bot_nickname: str,
    allowed_skills: list | None = None,
) -> str:
    tool_strength = normalize_constraint_strength(getattr(config, "toolCallConstraintStrength", None))
    emoji_strength = normalize_constraint_strength(getattr(config, "emojiUsageConstraintStrength", None))
    audio_strength = normalize_constraint_strength(getattr(config, "audioUsageConstraintStrength", None))
    markdown_strength = normalize_constraint_strength(getattr(config, "markdownUsageConstraintStrength", None))

    sections = [
        build_persona_section(getattr(config, "persona", "")),
        build_response_format_section(
            config,
            tool_strength,
            emoji_strength,
            audio_strength,
            markdown_strength,
            allowed_skills=allowed_skills,
        ),
    ]
    return "\n\n".join(s for s in sections if s)
