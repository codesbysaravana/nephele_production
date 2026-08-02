"""
Proctoring events table — logs client-side signals.
No analysis or verdicts — pure event capture.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

_DB_PATH = Path(__file__).parent.parent / "interview.db"


class ProctorDB:
    """Stores proctoring events from the client."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._path = str(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fact_proctor_events (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp  TEXT NOT NULL
                )
            """)

    # DECISION: Only allow known event types to prevent garbage data.
    VALID_EVENTS = {"tab_blur", "tab_focus", "no_face", "multiple_faces", "face_restored"}

    def log_event(self, user_id: str, session_id: str, event_type: str) -> bool:
        """Log a proctor event. Returns False if event_type is invalid."""
        if event_type not in self.VALID_EVENTS:
            return False
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO fact_proctor_events (user_id, session_id, event_type, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (user_id, session_id, event_type, now),
            )
        return True

    def get_session_events(self, session_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_type, timestamp FROM fact_proctor_events "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session_summary(self, session_id: str) -> dict:
        """Count each event type for a session — used by readiness ML later."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_type, COUNT(*) as cnt FROM fact_proctor_events "
                "WHERE session_id = ? GROUP BY event_type",
                (session_id,),
            ).fetchall()
            return {r["event_type"]: r["cnt"] for r in rows}
