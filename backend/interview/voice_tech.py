"""
Voice-driven technical interview — adaptive questions spoken aloud,
user answers via voice, system scores and asks next question.
"""

import asyncio
import logging
from fastapi import WebSocket

from ai_services.tts import generate_speech
from interview.tech_pipeline import generate_question, score_answer
from interview.resume_db import ResumeDB

logger = logging.getLogger(__name__)

MAX_TECH_QUESTIONS = 8


class VoiceTech:
    """Voice-driven technical interview: ask → listen → score → repeat."""

    def __init__(self, user_id: str, session_id: str, ws: WebSocket):
        self._user_id = user_id
        self._session_id = session_id
        self._ws = ws
        self._db = ResumeDB()
        self._current_question: str | None = None
        self._questions_asked = 0
        self._complete = False
        self._scores: list[int] = []

    @property
    def is_complete(self) -> bool:
        return self._complete

    async def start(self):
        """Begin the technical interview round."""
        resume = await asyncio.to_thread(self._db.get_resume, self._user_id)
        if not resume:
            # VOICE-WIRE: No resume → skip tech round with voice feedback
            audio = await generate_speech(
                "I don't have your resume on file, so I'll skip the technical round. "
                "Let me give you your overall summary."
            )
            if audio: await self._ws.send_bytes(audio)
            self._complete = True
            return

        intro = "Great job on the MCQ round. Now let's do the technical interview. I'll ask you questions based on your resume. Take your time and explain your thinking."
        audio = await generate_speech(intro)
        if audio: await self._ws.send_bytes(audio)
        await self._ask_next_question()

    async def handle_spoken_answer(self, transcript: str):
        """Score the spoken answer, then ask the next question or end."""
        if self._complete or not self._current_question:
            return

        # VOICE-WIRE: Score via LLM (async, non-blocking)
        result = await score_answer(
            self._user_id, self._session_id,
            self._current_question, transcript,
        )
        self._scores.append(result["score"])

        # VOICE-WIRE: Brief acknowledgment (don't reveal score)
        if result["score"] >= 4:
            ack = "Good answer. Let's move on."
        elif result["score"] >= 3:
            ack = "Okay, let's continue."
        else:
            ack = "Alright, let's try another one."

        audio = await generate_speech(ack)
        if audio: await self._ws.send_bytes(audio)

        self._questions_asked += 1
        if self._questions_asked >= MAX_TECH_QUESTIONS:
            await self._end_round()
        else:
            await self._ask_next_question()

    async def _ask_next_question(self):
        """Generate and speak the next adaptive question."""
        q = await generate_question(self._user_id, self._session_id)
        if not q:
            await self._end_round()
            return

        self._current_question = q["question"]
        # VOICE-WIRE: Speak the question via TTS
        audio = await generate_speech(q["question"])
        if audio: await self._ws.send_bytes(audio)

    async def _end_round(self):
        """Summarize and switch back to conversation mode."""
        self._complete = True
        avg_score = sum(self._scores) / len(self._scores) if self._scores else 0

        if avg_score >= 4:
            summary = "Excellent performance on the technical round. You showed strong understanding across the topics we covered."
        elif avg_score >= 3:
            summary = "Good effort on the technical round. You demonstrated solid knowledge with some areas to strengthen."
        else:
            summary = "The technical round is complete. I'd suggest reviewing the topics we discussed for deeper understanding."

        summary += " The interview is now complete. You can ask me anything or say goodbye."
        audio = await generate_speech(summary)
        if audio: await self._ws.send_bytes(audio)
        logger.info(f"[VOICE-TECH] user={self._user_id} questions={self._questions_asked} avg={avg_score:.1f}")
