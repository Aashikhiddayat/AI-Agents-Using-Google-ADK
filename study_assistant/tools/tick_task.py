"""Record a daily completion check-in and detect sustained missed work."""

from datetime import date, timedelta

from google.adk.tools.tool_context import ToolContext

from ._plan import day_tasks, plan_tasks


def tick_task(completed_count: int, total_count: int, tool_context: ToolContext) -> dict:
    """Log how many of today's study tasks were completed and calculate the completion rate."""
    if total_count <= 0 or completed_count < 0 or completed_count > total_count:
        return {"error": "completed_count must be between 0 and total_count, and total_count must be positive."}
    rate = round(completed_count / total_count, 2)
    entry = {"date": date.today().isoformat(), "completed": completed_count, "total": total_count, "completion_rate": rate}
    log = list(tool_context.state.get("progress_log", []))
    if log and log[-1].get("date") == entry["date"]:
        log[-1] = entry
    else:
        log.append(entry)
    tool_context.state["progress_log"] = log[-14:]
    recent = log[-2:]
    consecutive_days = len(recent) == 2 and date.fromisoformat(recent[1]["date"]) - date.fromisoformat(recent[0]["date"]) == timedelta(days=1)
    behind = consecutive_days and all(item["completion_rate"] < 0.8 for item in recent)
    missed = day_tasks(plan_tasks(str(tool_context.state.get("study_plan", ""))), date.today()) if behind else []
    if behind:
        tool_context.state["temp:missed_work"] = missed
        tool_context.state["replanning_needed"] = {"missed_tasks": missed, "reason": "Completion below 80% for two consecutive check-ins."}
    return {**entry, "replanning_needed": behind, "message": "Two consecutive low-completion days detected." if behind else "Progress saved."}
