"""
Voice-driven MCQ round — reads questions aloud, interprets spoken answers via LLM.
"""

import os
import json
import time
import asyncio
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv
from fastapi import WebSocket

from ai_services.tts import generate_speech
from interview.mcq_db import McqDB

load_dotenv()
logger = logging.getLogger(__name__)
_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MCQ_ROUND_DURATION_S = 600
QUESTIONS_PER_ROUND = 10


class VoiceMcq:
    """Voice-driven MCQ: reads questions aloud, parses spoken answers via LLM."""

    def __init__(self, user_id: str, session_id: str, ws: WebSocket):
        self._user_id = user_id
        self._session_id = session_id
        self._ws = ws
        self._db = McqDB()
        self._questions: list[dict] = []
        self._current_idx = 0
        self._start_time: float = 0
        self._question_sent_at: float = 0
        self._score = 0
        self._complete = False

    @property
    def is_complete(self) -> bool:
        return self._complete

    async def start(self, topic: str | None = None):
        """Begin MCQ round: fetch questions, speak the first one."""
        self._questions = await asyncio.to_thread(
            self._db.get_questions_by_topic, topic, QUESTIONS_PER_ROUND
        )
        if not self._questions:
            audio = await generate_speech("I don't have any questions loaded. Let me skip ahead.")
            if audio: await self._ws.send_bytes(audio)
            self._complete = True
            return

        self._start_time = time.time()
        self._current_idx = 0
        self._score = 0
        # VOICE-WIRE: Announce MCQ start via TTS
        intro = f"Let's start the MCQ round. You have 10 minutes for {len(self._questions)} questions. Here's the first one."
        audio = await generate_speech(intro)
        if audio: await self._ws.send_bytes(audio)
        await self._speak_current_question()

    async def handle_spoken_answer(self, transcript: str):
        """Interpret the user's spoken answer using LLM, score it, advance."""
        if self._complete:
            return
        if self._time_expired():
            await self._end_round("time_up")
            return

        q = self._questions[self._current_idx]
        options = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
        time_taken_ms = int((time.time() - self._question_sent_at) * 1000)

        # VOICE-WIRE: Use LLM to interpret which option the user meant
        chosen = await self._interpret_answer(transcript, options)
        is_correct = chosen == q["correct_answer"].strip().upper()
        if is_correct:
            self._score += 1

        await asyncio.to_thread(
            self._db.log_attempt, self._user_id, self._session_id,
            q["question_id"], chosen, is_correct, time_taken_ms,
        )

        # VOICE-WIRE: Speak result and advance
        if is_correct:
            feedback = "Correct!"
        else:
            correct_text = options[ord(q["correct_answer"].upper()) - ord("A")]
            feedback = f"That's incorrect. The answer was {correct_text}."

        audio = await generate_speech(feedback)
        if audio: await self._ws.send_bytes(audio)

        self._current_idx += 1
        if self._current_idx >= len(self._questions) or self._time_expired():
            await self._end_round("completed")
        else:
            await self._speak_current_question()

    async def _speak_current_question(self):
        """Read the current question and options aloud via TTS."""
        q = self._questions[self._current_idx]
        options = json.loads(q["options"]) if isinstance(q["options"], str) else q["options"]
        self._question_sent_at = time.time()

        labels = ["A", "B", "C", "D"]
        opts_text = ". ".join(f"{labels[i]}: {options[i]}" for i in range(len(options)))
        speech = f"Question {self._current_idx + 1}. {q['question']}. Options: {opts_text}"

        audio = await generate_speech(speech)
        if audio: await self._ws.send_bytes(audio)

    async def _interpret_answer(self, transcript: str, options: list) -> str:
        """Use LLM to map spoken text to A/B/C/D."""
        labels = ["A", "B", "C", "D"]
        opts_str = "\n".join(f"{labels[i]}: {options[i]}" for i in range(len(options)))

        # VOICE-WIRE: LLM interprets fuzzy spoken input into exact option letter
        response = await _client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"The user is answering a multiple-choice question. Map their spoken answer to exactly one letter: A, B, C, or D. Reply with ONLY the letter.\n\nOptions:\n{opts_str}"},
                {"role": "user", "content": transcript},
            ],
            max_tokens=2,
            temperature=0,
        )
        letter = response.choices[0].message.content.strip().upper()
        return letter if letter in labels else "X"

    async def _end_round(self, reason: str):
        self._complete = True
        summary = f"MCQ round complete. You scored {self._score} out of {len(self._questions)}. "
        if reason == "time_up":
            summary += "Time ran out. "
        summary += "Now let's move to the technical interview."
        audio = await generate_speech(summary)
        if audio: await self._ws.send_bytes(audio)
        logger.info(f"[VOICE-MCQ] user={self._user_id} score={self._score}/{len(self._questions)}")

    def _time_expired(self) -> bool:
        return (time.time() - self._start_time) >= MCQ_ROUND_DURATION_S
