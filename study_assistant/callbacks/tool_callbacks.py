"""Tool-call observability stored in temporary session state."""

from __future__ import annotations

from typing import Any


def _append(state: Any, item: dict) -> None:
    trace = list(state.get("temp:trace", []))
    state["temp:trace"] = (trace + [item])[-30:]


def before_tool_callback(tool: Any, args: dict, tool_context: Any) -> None:
    """Log tool name and input before execution."""
    _append(tool_context.state, {"event": "tool_start", "tool": tool.name, "input": args})


def after_tool_callback(tool: Any, args: dict, tool_context: Any, tool_response: dict) -> None:
    """Log the result shape without duplicating a full plan into the trace."""
    _append(tool_context.state, {"event": "tool_end", "tool": tool.name, "result_keys": list((tool_response or {}).keys())})
