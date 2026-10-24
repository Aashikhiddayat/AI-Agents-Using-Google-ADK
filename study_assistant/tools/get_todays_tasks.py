"""Extract today's work from the shared plan state."""

from datetime import date

from google.adk.tools.tool_context import ToolContext

from ._plan import day_tasks, plan_tasks


def get_todays_tasks(tool_context: ToolContext) -> dict:
    """List today's or next scheduled tasks from the current study plan."""
    tasks = plan_tasks(
        str(tool_context.state.get("study_plan", "")),
        str(tool_context.state.get("study_start_time", "")),
    )
    today = date.today()
    selected = day_tasks(tasks, today)
    tool_context.state["tasks_today"] = selected
    return {"date": today.isoformat(), "tasks": selected, "count": len(selected)}
