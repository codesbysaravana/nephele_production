"""
Resume and technical interview tables — parsed_resumes + fact_interview_qa.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

_DB_PATH = Path(__file__).parent.parent / "interview.db"


class ResumeDB:
    """CRUD for parsed resumes and interview Q&A scoring."""

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
                CREATE TABLE IF NOT EXISTS parsed_resumes (
                    user_id     TEXT PRIMARY KEY,
                    raw_text    TEXT NOT NULL,
                    skills      TEXT NOT NULL,
                    projects    TEXT NOT NULL,
                    experience  TEXT NOT NULL,
                    parsed_at   TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fact_interview_qa (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id          TEXT NOT NULL,
                    session_id       TEXT NOT NULL,
                    question         TEXT NOT NULL,
                    answer_transcript TEXT,
                    score            INTEGER CHECK(score BETWEEN 1 AND 5),
                    notes            TEXT,
                    asked_at         TEXT NOT NULL
                );
            """)

    # --- Resumes ---

    def save_parsed_resume(self, user_id: str, raw_text: str,
                           skills: list, projects: list, experience: list):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO parsed_resumes
                (user_id, raw_text, skills, projects, experience, parsed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, raw_text, json.dumps(skills),
                  json.dumps(projects), json.dumps(experience), now))

    def get_resume(self, user_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM parsed_resumes WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "user_id": row["user_id"],
                "skills": json.loads(row["skills"]),
                "projects": json.loads(row["projects"]),
                "experience": json.loads(row["experience"]),
            }

    # --- Interview Q&A ---

    def log_qa(self, user_id: str, session_id: str, question: str,
               answer_transcript: str | None, score: int | None, notes: str | None):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO fact_interview_qa
                (user_id, session_id, question, answer_transcript, score, notes, asked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, session_id, question, answer_transcript, score, notes, now))

    def get_session_qa(self, session_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT question, answer_transcript, score, notes FROM fact_interview_qa "
                "WHERE session_id = ? ORDER BY id ASC", (session_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_user_qa_history(self, user_id: str, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT question, answer_transcript, score, notes FROM fact_interview_qa "
                "WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]
