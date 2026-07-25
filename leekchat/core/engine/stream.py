from __future__ import annotations

from typing import Any


def create_think_tag_stream_filter() -> Any:
    state = {"buffer": "", "inside": False}

    def push(delta: str, force: bool) -> str:
        state["buffer"] += delta or ""
        output = ""
        while state["buffer"]:
            if state["inside"]:
                close = state["buffer"].lower().find("</think>")
                if close < 0:
                    if force:
                        state["buffer"] = ""
                    break
                state["buffer"] = state["buffer"][close + len("</think>"):]
                state["inside"] = False
                continue

            lower = state["buffer"].lower()
            open_idx = lower.find("<think")
            if open_idx < 0:
                if force:
                    output += state["buffer"]
                    state["buffer"] = ""
                else:
                    keep = _keep_prefix(state["buffer"], "<think")
                    output += state["buffer"][: len(state["buffer"]) - len(keep)]
                    state["buffer"] = keep
                break

            output += state["buffer"][:open_idx]
            rest = state["buffer"][open_idx + len("<think"):]
            close_char = rest.find(">")
            if close_char < 0:
                if force:
                    state["buffer"] = ""
                else:
                    state["buffer"] = "<think" + rest
                break
            state["buffer"] = rest[close_char + 1:]
            state["inside"] = True

        return output

    return {"push": push}


def _keep_prefix(text: str, tag: str) -> str:
    max_len = min(len(text), len(tag) - 1)
    lower_text = text.lower()
    lower_tag = tag.lower()
    for length in range(max_len, 0, -1):
        if lower_tag.startswith(lower_text[-length:]):
            return text[-length:]
    return ""