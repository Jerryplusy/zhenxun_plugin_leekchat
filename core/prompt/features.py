from __future__ import annotations


WEB_SEARCH_LINE: dict[str, str] = {
    "high": "- When facts may be outdated or uncertain, proactively call web_search instead of guessing.",
    "medium": "- Use web_search when current or external info is needed.",
    "low": "- Use web_search only when the user explicitly needs external/current information.",
}


AUDIO_MODE_LINE: dict[str, str] = {
    "high": "- Use voice sparingly. Only use it when spoken delivery is clearly better than text, such as a greeting, a sharp emotional reaction, or a daily phrase.",
    "medium": "- You may use voice for greetings, reactions, calls, confirmations, or comforting words, but stay selective.",
    "low": "- When a short spoken reaction would make the conversation feel more natural or vivid, you can use voice more freely.",
}


MARKDOWN_MODE_LINE: dict[str, str] = {
    "high": "- Prefer normal chat text. Use Markdown only when the reply truly needs structured presentation, such as a tutorial, comparison, detailed explanation, code sample or processing large amounts of data, such as after a web search or viewing a webpage.",
    "medium": "- Use Markdown when your responses require a structured presentation.",
    "low": "- Use Markdown freely where it can make your responses clearer.",
}


TOOL_INTENSITY_BLOCK: dict[str, str] = {
    "high": """
### Tool Usage Intensity
- Be proactive with tools for uncertain facts, external info, verification, and current events.
- Prefer validating with tools over guessing.
- If web searches fail to produce a useful answer after about 2-3 attempts, stop searching and reply directly based on what you already know or what you have already found.""",
    "medium": """
### Tool Usage Intensity
- Use tools when clearly useful for correctness, verification, or missing context.
- If web searches still do not produce a useful answer after about 2-3 attempts, stop searching and give a direct reply instead of continuing to try more keywords.""",
    "low": """
### Tool Usage Intensity
- Prefer direct chat responses first.
- Use tools only when strictly necessary.""",
}


EMOJI_MODE_LINE: dict[str, str] = {
    "high": "- Do not use stickers in consecutive chat turns. Use a sticker only when you are in an emotionally intense state.",
    "medium": "- Do not use stickers in consecutive chat turns.",
    "low": "- Feel free to use a sticker whenever you want.",
}


REPLY_MULTIUSER_LENGTH: dict[str, str] = {
    "high": "Keep it extremely brief. Prefer one short sentence; max two short lines.",
    "medium": "Keep it brief and conversational. One or two sentences max. Don't try to be comprehensive - just pick one thing to respond to or make a general comment that fits the vibe.",
    "low": "Keep it natural and focused on one key point instead of covering everything.",
}


REPLY_SINGLE_TOOL: dict[str, str] = {
    "high": "If the user asks for facts, verification, or external info, proactively use suitable tools. Avoid guessing when tools can validate.",
    "medium": "If the user asks for help, use recent chat history and suitable tools when needed to answer accurately. Avoid vague or incorrect info.",
    "low": "If the user asks for help, prioritize direct conversational replies first. Use tools only when clearly necessary.",
}


REPLY_SINGLE_LENGTH: dict[str, str] = {
    "high": "Length target: one short sentence preferred, max two short lines.",
    "medium": "Length target: concise reply, usually within 1-2 short paragraphs.",
    "low": "",
}


COMMENT_LENGTH: dict[str, str] = {
    "high": "Length target: keep it very short, ideally one sentence, max two short lines. If there are multiple messages, summarize into one brief reply.",
    "medium": "Important! Messages must be concise and impactful, not exceeding two sentences. If there are multiple messages, summarize and reply concisely.",
    "low": "If there are multiple messages, prefer one merged response instead of replying one by one.",
}


IDLE_LENGTH: dict[str, str] = {
    "high": 'Length target: one short sentence only. Do NOT say things like "群里好久没人说话了" or "大家怎么都不说话了".',
    "medium": 'Important!! Please keep your messages extremely concise. Use no more than one sentence to reply to the person you most want to reply to, or two short paragraphs for a brief group-level comment. Do NOT say things like "群里好久没人说话了" or "大家怎么都不说话了".',
    "low": "Reply naturally and quickly; avoid mentioning that the group was quiet.",
}


REVIEW_MULTI_LENGTH: dict[str, str] = {
    "high": "CRITICAL: Reply once only, and keep it to one short sentence (max two short lines).",
    "medium": "CRITICAL: Do NOT try to reply to each message or each person separately. Give ONE brief, casual response that fits the overall conversation. Pick one thing to comment on or just say something general. Keep it to a single sentence or two at most.",
    "low": "Reply once for the whole group instead of replying person-by-person.",
}


REVIEW_SINGLE_LENGTH: dict[str, str] = {
    "high": "Respond naturally in one short message, preferably one sentence.",
    "medium": "Please respond reasonably and naturally in context. Keep the message concise, since you've already said it, and it must fit in a single message.",
    "low": "Respond naturally in context and avoid repeating old wording.",
}


POKED_LENGTH: dict[str, str] = {
    "high": "Keep this very short: one brief sentence.",
    "medium": "",
    "low": "",
}


REPLY_STYLE_LENGTH: dict[str, str] = {
    "high": "Keep replies very short. Prefer one short sentence; max two short lines.",
    "medium": "Keep replies concise and conversational. Avoid long paragraphs unless the topic demands it.",
    "low": "Keep replies natural and conversational. Do not be verbose without purpose.",
}


def build_web_search_feature_section(config, tool_strength: str = "medium") -> str:
    if not getattr(getattr(config, "searxng", None), "enabled", False):
        return ""
    return f"""
### Web Search Tool
- web_search: Use this when you need current or external information that is not in chat history.
{WEB_SEARCH_LINE.get(tool_strength, WEB_SEARCH_LINE["medium"])}"""


def build_web_read_feature_section(config, _tool_strength: str = "medium") -> str:
    if not getattr(getattr(config, "webReader", None), "enabled", False):
        return ""
    searxng_enabled = getattr(getattr(config, "searxng", None), "enabled", False)
    independent_use_line = (
        "- web_search and web_read_page are independent. Use web_search when you need to discover URLs; use web_read_page directly when the user already gave a URL."
        if searxng_enabled
        else "- web_read_page can be used directly when the user provides a URL."
    )
    return f"""
### Web Reading Tool
- web_read_page: Read a webpage URL, extract the main content, and return a compressed content block that preserves as much page information as possible.
{independent_use_line}
- Only set render_js=true when the page clearly needs JavaScript rendering, because it costs much more CPU and memory."""


def build_recall_memory_feature_section(config) -> str:
    if not getattr(getattr(config, "memory", None), "enabled", False):
        return ""
    return """
### Memory Recall Tool
- recall_memory: Delegate recall to a memory worker model. Pass a clear recall question and let the worker search historical logs.
- Use recall_memory ONLY when there is explicit need to recall past content and required information is clearly missing from current context.
- Do NOT call recall_memory for every question.
- The worker returns historical logs with timestamps; treat them as past records, not newly sent messages."""