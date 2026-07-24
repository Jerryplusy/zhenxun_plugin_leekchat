from __future__ import annotations


MARKDOWN_OPEN_TAG = "<MARKDOWN>"
MARKDOWN_CLOSE_TAG = "</MARKDOWN>"


def split_outgoing_units(text: str) -> list[str]:
    normalized = str(text or "").replace("\r", "")
    result: list[str] = []
    buffer = ""
    inside_markdown = False

    i = 0
    while i < len(normalized):
        if not inside_markdown and normalized.startswith(MARKDOWN_OPEN_TAG, i):
            if buffer.strip():
                result.append(buffer.strip())
            buffer = MARKDOWN_OPEN_TAG
            inside_markdown = True
            i += len(MARKDOWN_OPEN_TAG)
            continue

        if inside_markdown and normalized.startswith(MARKDOWN_CLOSE_TAG, i):
            buffer += MARKDOWN_CLOSE_TAG
            if buffer.strip():
                result.append(buffer.strip())
            buffer = ""
            inside_markdown = False
            i += len(MARKDOWN_CLOSE_TAG)
            continue

        ch = normalized[i]
        if not inside_markdown and ch == "\n":
            if buffer.strip():
                result.append(buffer.strip())
            buffer = ""
            i += 1
            continue

        buffer += ch
        i += 1

    if buffer.strip():
        result.append(buffer.strip())
    return result


def consume_complete_stream_units(buffer: str, force: bool) -> dict:
    rest = str(buffer or "").replace("\r", "")
    units: list[str] = []

    while True:
        while rest.startswith("\n"):
            rest = rest[1:]
        if not rest:
            break
        next_unit = _take_next_stream_unit(rest, force)
        if not next_unit:
            break
        units.append(next_unit["unit"])
        rest = next_unit["rest"]

    return {"units": units, "rest": rest}


def extract_standalone_markdown_block(text: str) -> str | None:
    trimmed = str(text or "").strip()
    if not trimmed.startswith(MARKDOWN_OPEN_TAG) or not trimmed.endswith(MARKDOWN_CLOSE_TAG):
        return None
    inner = trimmed[len(MARKDOWN_OPEN_TAG):trimmed.rfind(MARKDOWN_CLOSE_TAG)]
    return inner.strip() or None


def summarize_markdown(markdown: str) -> str:
    lines = [
        line.strip()
        for line in str(markdown or "").replace("\r", "").split("\n")
        if line.strip()
    ]
    heading = next((line for line in lines if line.startswith("#")), None)
    if heading:
        return heading.lstrip("#").strip()[:40]
    first_line = next((line for line in lines if not line.startswith("```")), None)
    if not first_line:
        return "Markdown"
    return (first_line.lstrip(">*-\\d.`").strip()[:40]) or "Markdown"


def _take_next_stream_unit(text: str, force: bool) -> dict | None:
    open_index = text.find(MARKDOWN_OPEN_TAG)
    newline_index = text.find("\n")

    if open_index == -1:
        if newline_index >= 0:
            return {
                "unit": text[:newline_index].strip(),
                "rest": text[newline_index + 1:],
            }
        if force and text.strip():
            return {"unit": text.strip(), "rest": ""}
        return None

    if newline_index >= 0 and newline_index < open_index:
        return {
            "unit": text[:newline_index].strip(),
            "rest": text[newline_index + 1:],
        }

    if open_index > 0:
        prefix = text[:open_index].strip()
        return (
            {"unit": prefix, "rest": text[open_index:]}
            if prefix
            else {"unit": "", "rest": text[open_index:]}
        )

    close_index = text.find(MARKDOWN_CLOSE_TAG, len(MARKDOWN_OPEN_TAG))
    if close_index < 0:
        if force and text.strip():
            return {"unit": text.strip(), "rest": ""}
        return None

    end_index = close_index + len(MARKDOWN_CLOSE_TAG)
    unit = text[:end_index].strip()
    rest = text[end_index:]
    while rest.startswith("\n"):
        rest = rest[1:]
    return {"unit": unit, "rest": rest}