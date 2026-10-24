"""Flag missed work for the planner without controlling external applications."""

from datetime import date, timedelta

from google.adk.tools.tool_context import ToolContext


def trigger_replanning(tool_context: ToolContext) -> dict:
    """Set temporary missed-work state when two recent check-ins are below 80 percent."""
    log = list(tool_context.state.get("progress_log", []))[-2:]
    consecutive_days = len(log) == 2 and date.fromisoformat(log[1]["date"]) - date.fromisoformat(log[0]["date"]) == timedelta(days=1)
    if not consecutive_days or not all(item["completion_rate"] < 0.8 for item in log):
        return {"replanning_needed": False, "message": "Replanning needs two consecutive check-ins below 80%."}
    missed = list(tool_context.state.get("temp:missed_work", []))
    tool_context.state["replanning_needed"] = {"missed_tasks": missed, "reason": "Completion below 80% for two consecutive check-ins."}
    return {"replanning_needed": True, "missed_tasks": missed}
