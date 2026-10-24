"""Streamlit interface for the Google ADK Study Assistant."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import date, timedelta
from typing import Any

import streamlit as st
from google.adk.runners import Runner
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from study_assistant.agent import personal_assistant, study_planner
from study_assistant.config import APP_NAME, REQUEST_TIMEOUT_SECONDS
from study_assistant.state.session_manager import get_or_create_session, get_session_service
from study_assistant.tools._plan import plan_tasks


st.set_page_config(page_title="Studyflow", page_icon="✦", layout="wide")
st.markdown(
    """<style>
    .block-container {max-width:1080px;padding-top:2.5rem;padding-bottom:3rem;}
    [data-testid="stSidebar"] {border-right:1px solid rgba(128,128,128,.16);}
    [data-testid="stSidebar"] .block-container {padding-top:1.25rem;}
    .brand {padding:.3rem 0 1.15rem;}.brand h1 {font-size:1.45rem;letter-spacing:-.04em;margin:0;}
    .brand p,.eyebrow,.muted {color:#8b8e99;font-size:.88rem;}
    .page-heading {padding:.2rem 0 1.45rem;}.page-heading h1 {font-size:2.5rem;letter-spacing:-.055em;margin:0 0 .45rem;}
    .page-heading p {color:#8b8e99;font-size:1rem;margin:0;}
    .task-card {border:1px solid rgba(124,108,255,.24);padding:.75rem .9rem;margin:.55rem 0;background:rgba(124,108,255,.07);border-radius:14px;}
    .stButton>button,.stFormSubmitButton>button {border-radius:12px;font-weight:650;min-height:2.7rem;}
    [data-testid="stSidebar"] .stButton>button {justify-content:flex-start;padding-left:.9rem;}
    [data-testid="stSidebar"] .stButton>button[kind="primary"] {box-shadow:0 7px 20px rgba(124,108,255,.18);}
    div[data-testid="stForm"] {border:1px solid rgba(128,128,128,.18);border-radius:18px;padding:1.35rem;background:rgba(128,128,128,.025);}
    </style>""",
    unsafe_allow_html=True,
)


@st.cache_resource
def session_service():
    return get_session_service()


async def ensure_session(user_id: str, session_id: str):
    return await get_or_create_session(session_service(), user_id, session_id)


def run(coroutine):
    return asyncio.run(coroutine)


def load_state(user_id: str, session_id: str) -> dict[str, Any]:
    return dict(run(ensure_session(user_id, session_id)).state)


async def load_plan_history(user_id: str) -> list[dict[str, str]]:
    """List saved plan sessions for the current student, newest first."""
    service = session_service()
    sessions = (await service.list_sessions(app_name=APP_NAME, user_id=user_id)).sessions
    history = []
    for item in reversed(sessions):
        session = await service.get_session(app_name=APP_NAME, user_id=user_id, session_id=item.id)
        plan = str(session.state.get("study_plan", "")) if session else ""
        if plan:
            subject = re.search(r"(?im)^\*{0,2}subject\*{0,2}\s*:\s*(.+)$", plan)
            title = subject.group(1).strip() if subject else "Study plan"
            history.append({"id": item.id, "title": title[:42]})
    return history


async def save_session_values(user_id: str, session_id: str, values: dict[str, str]) -> None:
    """Persist student-provided preferences before an agent uses them."""
    service = session_service()
    session = await ensure_session(user_id, session_id)
    await service.append_event(
        session,
        Event(
            author="streamlit",
            invocation_id=str(uuid.uuid4()),
            actions=EventActions(stateDelta=values),
        ),
    )


def start_new_session() -> None:
    """Widget callback: runs before Streamlit creates the session-id widget."""
    st.session_state["adk_session_id"] = f"study-{uuid.uuid4().hex[:8]}"
    st.session_state["chat"] = []
    st.session_state["view"] = "plan"


def open_saved_plan(session_id: str) -> None:
    """Widget callback for selecting a saved plan from the sidebar."""
    st.session_state["adk_session_id"] = session_id
    st.session_state["chat"] = []
    st.session_state["view"] = "view"


def set_view(view: str) -> None:
    """Switch workspace sections through a callback-safe session value."""
    st.session_state["view"] = view


async def send(prompt: str, agent: Any, user_id: str, session_id: str, status) -> str:
    service = session_service()
    await ensure_session(user_id, session_id)
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=service)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    reply_parts = []
    stage_labels = {
        "coordinator": "Understanding your study requirements…",
        "planning": "Planning your study approach…",
        "topic_agent": "Prioritising topics…",
        "practice_agent": "Choosing practice activities…",
        "schedule_agent": "Building your schedule…",
        "study_plan_writer": "Writing your study plan…",
        "review_agent": "Reviewing the plan…",
        "personal_assistant": "Preparing your answer…",
    }

    async def collect():
        async for event in runner.run_async(user_id=user_id, session_id=session_id, invocation_id=str(uuid.uuid4()), new_message=message):
            author = getattr(event, "author", "")
            if author in stage_labels:
                status.info(stage_labels[author])
            parts = getattr(getattr(event, "content", None), "parts", []) or []
            if any(getattr(part, "function_call", None) for part in parts):
                status.info("Using your study tools…")
            if any(getattr(part, "function_response", None) for part in parts):
                status.info("Preparing your answer…")
            if event.is_final_response() and event.content:
                visible = "".join(
                    part.text or ""
                    for part in parts
                    if not getattr(part, "thought", False)
                )
                if visible:
                    reply_parts.append(visible)

    await asyncio.wait_for(collect(), timeout=REQUEST_TIMEOUT_SECONDS)
    return "\n".join(part for part in reply_parts if part).strip() or "Done."


def student_facing_plan(plan: str) -> str:
    """Never render a model thinking block, even if a provider returns one."""
    clean = _safe_ui_text(plan)
    heading = re.search(r"(?im)^#\s*study plan\s*$", clean)
    if heading:
        return clean[heading.start():]
    if re.search(r"(?i)(thinking process|analyze user input|determine study plan)", clean):
        return ""
    return clean


def student_facing_reply(reply: str) -> str:
    """Remove implementation details if a model accidentally exposes them."""
    if "tick_task" in reply.lower():
        return (
            "To record a study check-in, write: `I completed 3 out of 5 tasks today.` "
            "I’ll save the completion rate and update your progress."
        )
    clean = _safe_ui_text(reply)
    replacements = {
        "tick_task": "check-in",
        "get_todays_tasks": "today's task list",
        "progress_report": "progress summary",
        "trigger_replanning": "plan update",
        "tool": "assistant",
    }
    for internal, friendly in replacements.items():
        clean = re.sub(rf"\b{internal}\b", friendly, clean, flags=re.IGNORECASE)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return clean or "I’ve completed that study action."


def _safe_ui_text(text: str) -> str:
    """Keep model implementation details out of the student-facing interface."""
    clean = re.sub(r"<(?:think|analysis)>.*?</(?:think|analysis)>", "", text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"```[\s\S]*?(?:```|$)", "", clean)
    internal_terms = ("tick_task", "get_todays_tasks", "progress_report", "trigger_replanning", "tool_context", "state_delta")
    kept, in_json = [], False
    code_line = re.compile(r"^\s*(?:from\s+\S+\s+import|import\s+\S+|def\s+\w+\(|class\s+\w+|return\b|async\s+def|await\b|try:|except\b|raise\b|print\(|self\.|[A-Za-z_]\w*\s*=)")
    for line in clean.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if any(term in lower for term in internal_terms) or code_line.match(line):
            continue
        if re.search(r"\b(?:here is|following|this is).*(?:code|json)\b", lower):
            continue
        if in_json:
            if "}" in stripped or "]" in stripped:
                in_json = False
            continue
        if re.match(r"^[{[]\s*(?:\"|')", stripped):
            if "}" not in stripped and "]" not in stripped:
                in_json = True
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def ask(prompt: str, agent: Any, user_id: str, session_id: str, initial_status: str) -> str:
    status = st.empty()
    status.info(initial_status)
    try:
        response = run(send(prompt, agent, user_id, session_id, status))
        status.empty()
        return response
    except TimeoutError:
        status.empty()
        return f"This request exceeded the {REQUEST_TIMEOUT_SECONDS}-second safety limit. Your previous plan remains unchanged."
    except Exception:
        status.empty()
        return "I couldn’t complete that request right now. Please try again."


if "user_id" not in st.session_state:
    st.session_state.user_id = "study_student"
if "adk_session_id" not in st.session_state:
    st.session_state.adk_session_id = f"study-{uuid.uuid4().hex[:8]}"
if "chat" not in st.session_state:
    st.session_state.chat = []
if "view" not in st.session_state:
    st.session_state.view = "plan"

with st.sidebar:
    st.markdown("<div class='brand'><h1>Studyflow <span style='color:#7c6cff'>✦</span></h1><p>Personal study workspace</p></div>", unsafe_allow_html=True)
    st.text_input("Student ID", key="user_id")
    st.button("＋  New study plan", type="primary", use_container_width=True, on_click=start_new_session)
    st.caption("WORKSPACE")
    for label, key, icon in [
        ("Plan builder", "plan", "✦"),
        ("Personal assistant", "assistant", "◌"),
        ("My study plan", "view", "▣"),
    ]:
        st.button(
            f"{icon}  {label}",
            key=f"nav-{key}",
            type="primary" if st.session_state.view == key else "secondary",
            use_container_width=True,
            on_click=set_view,
            args=(key,),
        )
    st.divider()
    st.caption("SAVED PLANS")
    saved_plans = run(load_plan_history(st.session_state["user_id"]))
    if saved_plans:
        for saved in saved_plans[:12]:
            st.button(
                "◻ " + saved["title"],
                key=f"saved-plan-{saved['id']}",
                use_container_width=True,
                disabled=saved["id"] == st.session_state["adk_session_id"],
                on_click=open_saved_plan,
                args=(saved["id"],),
            )
    else:
        st.caption("Plans you build will appear here.")
    st.divider()
    st.caption("Study-only automation: planning, check-ins, tracking, and replanning. No access to other apps.")

user_id, session_id = st.session_state.user_id, st.session_state.adk_session_id
state = load_state(user_id, session_id)
page = st.session_state.view

if page == "plan":
    st.markdown("<div class='page-heading'><h1>Build a study plan</h1><p>Tell us what you need to learn and when your exam is. We’ll turn it into a realistic day-by-day schedule.</p></div>", unsafe_allow_html=True)
    with st.form("planner"):
        subject = st.text_input("Subject or course", placeholder="Enter your subject or course name")
        topics = st.text_area("Exact chapters or topics", placeholder="List only the chapters or topics you need to study")
        study_material = st.text_area("Study material or syllabus (optional)", placeholder="Book chapters, unit names, notes, question-paper focus, or links")
        first, second, third = st.columns(3)
        with first:
            exam_date = st.date_input("Exam date", value=date.today() + timedelta(days=15), min_value=date.today())
        with second:
            daily_hours = st.number_input("Hours each day", min_value=0.5, max_value=16.0, value=3.0, step=0.5)
        with third:
            level = st.selectbox("Current level", ["Beginner", "Intermediate", "Advanced"])
        study_start = st.time_input("Preferred daily study start time", value=None, help="The daily schedule will begin at this local time.")
        submitted = st.form_submit_button("Create my study plan  →", type="primary", use_container_width=True)
    if submitted:
        if not subject.strip() or not topics.strip() or study_start is None:
            st.warning("Add a subject, topics, and your study start time.")
        else:
            start_text = study_start.strftime("%H:%M")
            run(save_session_values(user_id, session_id, {"study_start_time": start_text}))
            material_text = f" Study material/syllabus: {study_material.strip()}." if study_material.strip() else ""
            prompt = (
                f"Today is {date.today().isoformat()}. I have a {subject.strip()} exam on {exam_date.isoformat()}. "
                f"I am {level.lower()} and can study {daily_hours} hours per day, starting at {start_text} local time. "
                f"Exact topics: {topics.strip()}.{material_text} Create my complete study plan using only these supplied details."
            )
            st.session_state.chat.append({"role": "user", "content": prompt})
            response = ask(prompt, study_planner, user_id, session_id, "Starting coordinator…")
            state = load_state(user_id, session_id)
            if state.get("study_plan"):
                st.session_state.view = "view"
                st.success("Plan saved. Opening your complete schedule…")
                st.rerun()
            else:
                st.error(student_facing_reply(response))

elif page == "assistant":
    st.markdown("<div class='page-heading'><h1>Personal assistant</h1><p>Ask about today’s work, record a check-in, or review your progress in natural language.</p></div>", unsafe_allow_html=True)
    with st.expander("How daily check-ins work"):
        st.markdown("""At the end of a study session, tell the assistant how much you completed. For example:

`I completed 3 out of 5 tasks today.`

It records your completion rate for today. Check in again tomorrow the same way. If completion is below 80% on two consecutive days, your remaining plan is automatically adjusted around missed work.""")
    quick = st.columns(2)
    choices = ["What should I do today?", "Check my weekly progress."]
    quick_prompt = next((text for column, text in zip(quick, choices) if column.button(text, use_container_width=True)), "")
    with st.form("assistant"):
        prompt = st.text_area("Message", placeholder="I completed 2 out of 4 tasks today")
        submitted = st.form_submit_button("Send message  →", type="primary", use_container_width=True)
    request = quick_prompt or (prompt.strip() if submitted else "")
    if request:
        st.session_state.chat.append({"role": "user", "content": request})
        response = ask(request, personal_assistant, user_id, session_id, "Personal Assistant is preparing your reply…")
        st.session_state.chat.append({"role": "assistant", "content": response})
        state = load_state(user_id, session_id)
        if state.get("replanning_needed"):
            replan = f"Today is {date.today().isoformat()}. Rebuild the current study plan. Account for missed tasks: {state.get('temp:missed_work', [])}. Keep the remaining deadline and requested topics from this plan: {state.get('study_plan', '')}"
            st.info("Two consecutive check-ins were below 80%. Rebuilding the plan around missed work…")
            response = ask(replan, study_planner, user_id, session_id, "Planner is adjusting your schedule…")
            state = load_state(user_id, session_id)
            if state.get("study_plan"):
                st.success("Your plan has been refreshed with missed work considered.")
    st.divider()
    for message in st.session_state.chat[-8:]:
        with st.chat_message(message["role"]):
            content = student_facing_reply(message["content"]) if message["role"] == "assistant" else message["content"]
            st.markdown(content)

else:
    st.markdown("<div class='page-heading'><h1>My study plan</h1><p>Your complete schedule and task timeline, kept ready whenever you return.</p></div>", unsafe_allow_html=True)
    plan = state.get("study_plan")
    visible_plan = student_facing_plan(str(plan or ""))
    if visible_plan:
        st.markdown(visible_plan)
        tasks = plan_tasks(str(plan))
        if tasks:
            st.divider()
            st.caption("Task timeline")
            for task in tasks:
                st.markdown(f"<div class='task-card'><b>{task['due_date']}</b> · {task['title']} <span style='color:#8b8e99'>({task['duration_minutes']} min)</span></div>", unsafe_allow_html=True)
    elif plan:
        st.warning("The previous request ended before a final plan was produced. Build the plan again.")
    else:
        st.info("No plan yet. Use “Build plan” to create your first one.")
    if state.get("progress_log"):
        st.divider()
        st.caption("Recent check-ins")
        st.dataframe(state["progress_log"][-7:], hide_index=True, use_container_width=True)
