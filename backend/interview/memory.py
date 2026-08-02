"""
Per-user scoped long-term memory, backed by SQLite.
Isolated from the global save_memory in openai.py.
"""

import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "interview.db"


class UserMemory:
    """Read/write user-scoped facts (survives restarts)."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._path = str(db_path)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    fact    TEXT NOT NULL
                )
            """)

    def get_facts(self, user_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT fact FROM user_memory WHERE user_id = ?", (user_id,)
            ).fetchall()
            return [r[0] for r in rows]

    def save_fact(self, user_id: str, fact: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO user_memory (user_id, fact) VALUES (?, ?)",
                (user_id, fact),
            )
