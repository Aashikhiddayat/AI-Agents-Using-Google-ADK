"""Shared helpers for the plan's machine-readable task manifest."""

from __future__ import annotations

import json
import re
from datetime import date


def plan_tasks(study_plan: str, study_start_time: str = "") -> list[dict]:
    """Read the final JSON task manifest from a study-plan response."""
    for block in reversed(re.findall(r"```json\s*(\{.*?\})\s*```", study_plan or "", re.DOTALL | re.IGNORECASE)):
        try:
            payload = json.loads(block)
            tasks = payload.get("tasks", [])
            if isinstance(tasks, list):
                return [
                    {
                        "id": str(item.get("id") or f"task-{index:02d}"),
                        "title": str(item["title"]),
                        "due_date": str(item["due_date"]),
                        "duration_minutes": int(item.get("duration_minutes", 45)),
                        "start_time": str(item.get("start_time", "")) if re.fullmatch(r"\d{1,2}:\d{2}", str(item.get("start_time", ""))) else "",
                        "notes": str(item.get("notes", "")),
                    }
                    for index, item in enumerate(tasks, 1)
                    if item.get("title") and item.get("due_date")
                ]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    # Plans made by an earlier version may have been cut off before their JSON
    # manifest. Recover visible time blocks so the daily assistant can still
    # show useful tasks for an older saved plan.
    dates = re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", study_plan or "")
    if dates:
        scheduled = []
        seen = set()
        allocation_heading = re.search(r"(?im)^##\s*realistic daily time allocation\s*$", study_plan)
        schedule_source = study_plan[allocation_heading.end():] if allocation_heading else study_plan
        pattern = re.compile(
            r"(?m)^\s*[-*]\s+\*{0,2}(\d{1,2}:\d{2})\s*(?:-|–|—|�)\s*"
            r"(\d{1,2}:\d{2})\s*:\*{0,2}\s*(.+?)\s*$"
        )
        for index, match in enumerate(pattern.finditer(schedule_source), 1):
            start_time, end_time, title = match.groups()
            key = (start_time, end_time, title)
            if key in seen:
                continue
            seen.add(key)
            start_minutes = _minutes(start_time)
            end_minutes = _minutes(end_time)
            if end_minutes > start_minutes:
                scheduled.append({
                    "id": f"scheduled-{index:02d}",
                    "title": _plain_text(title),
                    "due_date": min(dates),
                    "duration_minutes": end_minutes - start_minutes,
                    "start_time": start_time.zfill(5),
                    "end_time": end_time.zfill(5),
                    "notes": "Imported from your saved study-plan schedule.",
                })
        if scheduled:
            # Older plans sometimes use 0:00 as a relative study offset. Shift
            # only when the student has explicitly selected a start time.
            if study_start_time and min(_minutes(task["start_time"]) for task in scheduled) == 0:
                base_minutes = _minutes(study_start_time)
                for task in scheduled:
                    shifted_start = _minutes(task["start_time"]) + base_minutes
                    task["start_time"] = _clock(shifted_start)
                    task["end_time"] = _clock(shifted_start + task["duration_minutes"])
            elif min(_minutes(task["start_time"]) for task in scheduled) == 0:
                for task in scheduled:
                    task["relative_start_time"] = task.pop("start_time")
                    task.pop("end_time", None)
            return scheduled
        subject = re.search(r"(?im)^\*{0,2}subject\*{0,2}\s*:\s*(.+)$", study_plan)
        label = subject.group(1).strip(" *") if subject else "your study plan"
        return [{
            "id": "plan-review",
            "title": f"Follow {label}",
            "due_date": min(dates),
            "duration_minutes": 60,
            "notes": "This is a fallback task for a plan created before task export was available.",
        }]
    return []


def _minutes(value: str) -> int:
    hours, minutes = value.split(":", 1)
    return int(hours) * 60 + int(minutes)


def _plain_text(value: str) -> str:
    """Remove Markdown from a task title."""
    return re.sub(r"\s+", " ", re.sub(r"[*`_]", "", value)).strip()


def _clock(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes % (24 * 60), 60)
    return f"{hours:02d}:{minutes:02d}"


def day_tasks(tasks: list[dict], day: date) -> list[dict]:
    """Return due/overdue work; otherwise surface the next scheduled work."""
    due = [task for task in tasks if task["due_date"] <= day.isoformat()]
    return due or tasks[:3]
