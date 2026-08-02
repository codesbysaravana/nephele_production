"""
Interview SQLite database — users, sessions, messages.
Completely isolated from attendance.db and the DWH.
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone

# DECISION: Separate DB file so interview data never collides with attendance.db.
_DB_PATH = Path(__file__).parent.parent / "interview.db"


class InterviewDB:
    """Thread-safe SQLite access — one connection per call (safe for ASGI)."""

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
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id    TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    college_id TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    timestamp  TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );
            """)

    # --- Users ---

    def get_or_create_user(self, user_id: str, name: str = "Anonymous",
                           college_id: str | None = None) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                return dict(row)
            conn.execute(
                "INSERT INTO users (user_id, name, college_id) VALUES (?, ?, ?)",
                (user_id, name, college_id),
            )
            return {"user_id": user_id, "name": name, "college_id": college_id}

    # --- Sessions ---

    def create_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, user_id, started_at) VALUES (?, ?, ?)",
                (session_id, user_id, now),
            )
        return session_id

    def get_latest_session(self, user_id: str) -> str | None:
        """Return the most recent session_id for a user, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_id FROM sessions WHERE user_id = ? ORDER BY started_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            return row["session_id"] if row else None

    # --- Messages ---

    def save_message(self, session_id: str, role: str, content: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )

    def get_session_messages(self, session_id: str) -> list[dict]:
        """Return all messages in a session ordered chronologically."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]
