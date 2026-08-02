"""
Feature extraction for the readiness ML model.
Pulls from fact_attempts, fact_interview_qa, and fact_proctor_events.
"""

import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "interview.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def extract_features(user_id: str) -> dict | None:
    """
    Build a feature dict for a user. Returns None if no data exists.
    Features designed to be predictive of interview readiness.
    """
    conn = _connect()

    # --- MCQ features ---
    mcq_rows = conn.execute(
        "SELECT correct, time_taken_ms FROM fact_attempts WHERE user_id = ?",
        (user_id,),
    ).fetchall()

    if not mcq_rows:
        conn.close()
        return None

    mcq_total = len(mcq_rows)
    mcq_correct = sum(1 for r in mcq_rows if r["correct"])
    mcq_accuracy = mcq_correct / mcq_total if mcq_total else 0
    mcq_avg_time_ms = sum(r["time_taken_ms"] for r in mcq_rows) / mcq_total

    # --- Per-topic MCQ accuracy ---
    topic_rows = conn.execute(
        """SELECT qb.topic, fa.correct
           FROM fact_attempts fa
           JOIN question_bank qb ON fa.question_id = qb.question_id
           WHERE fa.user_id = ?""",
        (user_id,),
    ).fetchall()

    topic_scores = {}
    for r in topic_rows:
        t = r["topic"]
        topic_scores.setdefault(t, {"correct": 0, "total": 0})
        topic_scores[t]["total"] += 1
        if r["correct"]:
            topic_scores[t]["correct"] += 1

    # --- Technical interview features ---
    qa_rows = conn.execute(
        "SELECT score FROM fact_interview_qa WHERE user_id = ? AND score IS NOT NULL",
        (user_id,),
    ).fetchall()

    tech_total = len(qa_rows)
    tech_avg_score = sum(r["score"] for r in qa_rows) / tech_total if tech_total else 0
    tech_high_count = sum(1 for r in qa_rows if r["score"] >= 4)

    # --- Proctor features ---
    proctor_rows = conn.execute(
        "SELECT event_type, COUNT(*) as cnt FROM fact_proctor_events "
        "WHERE user_id = ? GROUP BY event_type",
        (user_id,),
    ).fetchall()

    proctor = {r["event_type"]: r["cnt"] for r in proctor_rows}
    tab_blurs = proctor.get("tab_blur", 0)
    no_face_events = proctor.get("no_face", 0)
    multi_face_events = proctor.get("multiple_faces", 0)

    conn.close()

    return {
        "mcq_accuracy": round(mcq_accuracy, 3),
        "mcq_total": mcq_total,
        "mcq_avg_time_ms": round(mcq_avg_time_ms, 1),
        "tech_avg_score": round(tech_avg_score, 2),
        "tech_total": tech_total,
        "tech_high_count": tech_high_count,
        "tab_blurs": tab_blurs,
        "no_face_events": no_face_events,
        "multi_face_events": multi_face_events,
        "topic_scores": topic_scores,
    }
