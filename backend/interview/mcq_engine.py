"""
MCQ round state machine — manages question delivery, timing, and scoring.
Communicates via JSON text frames over the WebSocket.
"""

import json
import time
import asyncio  # AUDIT-FIX-1: for to_thread wrapping
import logging
from fastapi import WebSocket

from interview.mcq_db import McqDB

logger = logging.getLogger(__name__)

# DECISION: 10 min = 600s hard limit. Timer enforced server-side.
MCQ_ROUND_DURATION_S = 600
QUESTIONS_PER_ROUND = 10


class McqEngine:
    """Per-session MCQ state. Created when client starts an MCQ round."""

    def __init__(self, user_id: str, session_id: str, ws: WebSocket):
        self._user_id = user_id
        self._session_id = session_id
        self._ws = ws
        self._db = McqDB()
        self._questions: list[dict] = []
        self._current_idx = 0
        self._start_time: float = 0
        self._question_sent_at: float = 0
        self._active = False
        self._score = 0

    @property
    def is_active(self) -> bool:
        return self._active

    async def start(self, topic: str | None = None):
        """Begin the MCQ round. Sends the first question."""
        self._questions = await asyncio.to_thread(self._db.get_questions_by_topic, topic, QUESTIONS_PER_ROUND)  # AUDIT-FIX-1
        if not self._questions:
            await self._send({"type": "mcq_error", "message": "No questions available"})
            return
        self._active = True
        self._start_time = time.time()
        self._current_idx = 0
        self._score = 0
        await self._send({
            "type": "mcq_started",
            "total_questions": len(self._questions),
            "duration_s": MCQ_ROUND_DURATION_S,
        })
        await self._send_current_question()

    async def handle_answer(self, answer: str):
        """Process a candidate's answer to the current question."""
        if not self._active:
            return
        if self._time_expired():
            await self._end_round("time_up")
            return

        q = self._questions[self._current_idx]
        time_taken_ms = int((time.time() - self._question_sent_at) * 1000)
        is_correct = answer.strip().upper() == q["correct_answer"].strip().upper()
        if is_correct:
            self._score += 1

        await asyncio.to_thread(  # AUDIT-FIX-1: async SQLite
            self._db.log_attempt, self._user_id, self._session_id, q["question_id"],
            answer, is_correct, time_taken_ms,
        )
        await self._send({
            "type": "mcq_result", "question_id": q["question_id"],
            "correct": is_correct, "correct_answer": q["correct_answer"],
            "time_taken_ms": time_taken_ms, "time_remaining_s": self._time_remaining(),
        })
        await self._advance()

    async def handle_skip(self):
        """Skip current question (logged as incorrect, no answer)."""
        if not self._active:
            return
        if self._time_expired():
            await self._end_round("time_up")
            return
        q = self._questions[self._current_idx]
        time_taken_ms = int((time.time() - self._question_sent_at) * 1000)
        await asyncio.to_thread(  # AUDIT-FIX-1: async SQLite
            self._db.log_attempt, self._user_id, self._session_id, q["question_id"],
            None, False, time_taken_ms,
        )
        await self._advance()

    async def _advance(self):
        """Move to next question or end the round."""
        self._current_idx += 1
        if self._current_idx >= len(self._questions):
            await self._end_round("completed")
        else:
            await self._send_current_question()

    async def _send_current_question(self):
        q = self._questions[self._current_idx]
        self._question_sent_at = time.time()
        options = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
        await self._send({
            "type": "mcq_question", "question_id": q["question_id"],
            "question_number": self._current_idx + 1,
            "total_questions": len(self._questions),
            "topic": q["topic"], "difficulty": q["difficulty"],
            "question": q["question"], "options": options,
            "time_remaining_s": self._time_remaining(),
        })

    async def _end_round(self, reason: str):
        self._active = False
        elapsed_s = int(time.time() - self._start_time)
        await self._send({
            "type": "mcq_complete", "reason": reason,
            "score": self._score, "total": len(self._questions),
            "attempted": self._current_idx, "time_taken_s": elapsed_s,
        })
        logger.info(f"[MCQ] user={self._user_id} score={self._score}/{len(self._questions)} reason={reason}")

    def _time_remaining(self) -> int:
        return max(0, int(MCQ_ROUND_DURATION_S - (time.time() - self._start_time)))

    def _time_expired(self) -> bool:
        return (time.time() - self._start_time) >= MCQ_ROUND_DURATION_S

    async def _send(self, payload: dict):
        await self._ws.send_text(json.dumps(payload))
