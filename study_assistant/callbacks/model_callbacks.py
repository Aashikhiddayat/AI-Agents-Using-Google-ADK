"""Lightweight model-call observability stored in temporary session state."""

from __future__ import annotations

import re
from typing import Any


def _text(value: Any) -> str:
    return "".join(getattr(part, "text", "") or "" for content in getattr(value, "contents", []) or [] for part in getattr(content, "parts", []) or [])


def _append(state: Any, item: dict) -> None:
    trace = list(state.get("temp:trace", []))
    state["temp:trace"] = (trace + [item])[-30:]


def before_model_callback(callback_context: Any, llm_request: Any) -> None:
    """Log agent name, approximate input tokens, and task preview before a model call."""
    text = _text(llm_request)
    _append(callback_context.state, {"event": "model_start", "agent": callback_context.agent_name, "input_tokens": len(text.split()), "task": text[:120]})


def after_model_callback(callback_context: Any, llm_response: Any) -> None:
    """Log approximate output tokens and any model reasoning payload after completion."""
    content = getattr(llm_response, "content", None)
    text = "".join(getattr(part, "text", "") or "" for part in getattr(content, "parts", []) or [])
    _append(callback_context.state, {"event": "model_end", "agent": callback_context.agent_name, "output_tokens": len(text.split()), "reasoning": bool(getattr(llm_response, "custom_metadata", None))})


def save_student_level(callback_context: Any) -> None:
    """Persist the level extracted by the coordinator for future sessions."""
    text = str(callback_context.state.get("coordinator_output", ""))
    match = re.search(r"current\s+level\s*:\s*([^\n]+)", text, re.IGNORECASE)
    if match:
        callback_context.state["user:student_level"] = match.group(1).strip(" .")
