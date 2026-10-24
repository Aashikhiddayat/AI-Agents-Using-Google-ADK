"""SQLite-backed ADK session management."""

from google.adk.sessions import DatabaseSessionService

from ..config import APP_NAME, DATA_DIR


def get_session_service() -> DatabaseSessionService:
    """Return the local persistent session service."""
    DATA_DIR.mkdir(exist_ok=True)
    return DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{(DATA_DIR / 'sessions.db').resolve().as_posix()}")


async def get_or_create_session(service: DatabaseSessionService, user_id: str, session_id: str):
    """Load one session or create it with no initial state."""
    session = await service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    return session or await service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
