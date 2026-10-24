"""Create a deterministic weekly study-progress summary."""

from google.adk.tools.tool_context import ToolContext


def progress_report(tool_context: ToolContext) -> dict:
    """Summarize up to seven recent completion check-ins from progress_log."""
    entries = list(tool_context.state.get("progress_log", []))[-7:]
    completed = sum(item["completed"] for item in entries)
    assigned = sum(item["total"] for item in entries)
    return {"check_ins": len(entries), "completed": completed, "assigned": assigned, "completion_rate": round(completed / assigned, 2) if assigned else 0, "history": entries}
