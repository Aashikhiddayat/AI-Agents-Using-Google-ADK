from datetime import date, timedelta
from types import SimpleNamespace

from study_assistant.tools._plan import plan_tasks
from study_assistant.tools.get_todays_tasks import get_todays_tasks
from study_assistant.tools.tick_task import tick_task


PLAN = '''Day 1
```json
{"tasks": [{"title": "Read OOP", "due_date": "2026-10-24", "start_time": "09:00", "duration_minutes": 60}]}
```'''

LEGACY_PLAN = """# Study Plan
## 2026-10-24
- **00:00 � 01:30:** Binary Search Tree fundamentals
- **01:45 � 03:00:** Binary Heap practice
"""


def context():
    return SimpleNamespace(state={"study_plan": PLAN})


def test_plan_manifest_is_readable():
    tasks = plan_tasks(PLAN)
    assert tasks[0]["title"] == "Read OOP"
    assert tasks[0]["duration_minutes"] == 60
    assert tasks[0]["start_time"] == "09:00"


def test_today_tasks_updates_shared_state():
    tool_context = context()
    result = get_todays_tasks(tool_context)
    assert result["count"] == 1
    assert tool_context.state["tasks_today"][0]["title"] == "Read OOP"


def test_legacy_plan_time_blocks_become_daily_tasks():
    tasks = plan_tasks(LEGACY_PLAN, "08:30")
    assert len(tasks) == 2
    assert tasks[0]["start_time"] == "08:30"
    assert tasks[0]["duration_minutes"] == 90


def test_two_low_checkins_request_replanning():
    tool_context = context()
    tool_context.state["progress_log"] = [{"date": (date.today() - timedelta(days=1)).isoformat(), "completed": 1, "total": 4, "completion_rate": 0.25}]
    result = tick_task(1, 4, tool_context)
    assert result["replanning_needed"] is True
    assert "temp:missed_work" in tool_context.state
