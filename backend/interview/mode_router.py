"""
Mode-based routing for the interview WebSocket session.
Routes STT transcripts to the correct handler based on session state.
"""

import asyncio
import logging
from fastapi import WebSocket

from interview.pipeline import run_interview_turn
from interview.voice_mcq import VoiceMcq
from interview.voice_tech import VoiceTech

logger = logging.getLogger(__name__)

# VOICE-WIRE: Trigger phrases detected in conversation mode to switch modes.
_INTERVIEW_TRIGGERS = ["start interview", "begin interview", "start the interview"]
_ATTENDANCE_TRIGGERS = ["take attendance", "scan attendance", "attendance mode"]


class ModeRouter:
    """Per-session state machine that routes STT transcripts by mode."""

    def __init__(self, user_id: str, session_id: str, ws: WebSocket, history: list):
        self._user_id = user_id
        self._session_id = session_id
        self._ws = ws
        self._history = history
        self._mode = "conversation"  # VOICE-WIRE: default mode
        self._mcq = VoiceMcq(user_id, session_id, ws)
        self._tech = VoiceTech(user_id, session_id, ws)

    @property
    def mode(self) -> str:
        return self._mode

    async def route_transcript(self, text: str):
        """Route an STT transcript to the correct handler based on current mode."""
        # VOICE-WIRE: dispatch based on session mode
        if self._mode == "conversation":
            await self._handle_conversation(text)
        elif self._mode == "mcq":
            await self._mcq.handle_spoken_answer(text)
            if self._mcq.is_complete:
                await self._transition_to_tech()
        elif self._mode == "tech_interview":
            await self._tech.handle_spoken_answer(text)
            if self._tech.is_complete:
                await self._transition_to_conversation()

    async def _handle_conversation(self, text: str):
        """Conversation mode: check for triggers, else pass to assistant."""
        lower = text.lower().strip()

        # VOICE-WIRE: detect "start interview" trigger
        if any(trigger in lower for trigger in _INTERVIEW_TRIGGERS):
            await self._transition_to_mcq()
            return

        # VOICE-WIRE: detect "take attendance" trigger
        if any(trigger in lower for trigger in _ATTENDANCE_TRIGGERS):
            import json
            await self._ws.send_text(json.dumps({"command": "route", "path": "#/attendance"}))
            return

        # Default: conversational assistant
        async for chunk in run_interview_turn(text, self._user_id, self._history):
            if isinstance(chunk, tuple):
                continue
            elif isinstance(chunk, str):
                await self._ws.send_text(chunk)
            else:
                await self._ws.send_bytes(chunk)

    async def _transition_to_mcq(self):
        """Switch to MCQ mode and speak the first question."""
        self._mode = "mcq"  # VOICE-WIRE: mode transition
        logger.info(f"[MODE] user={self._user_id} → mcq")
        await self._mcq.start()

    async def _transition_to_tech(self):
        """MCQ complete → switch to tech interview."""
        self._mode = "tech_interview"  # VOICE-WIRE: mode transition
        logger.info(f"[MODE] user={self._user_id} → tech_interview")
        await self._tech.start()

    async def _transition_to_conversation(self):
        """Tech complete → switch back to conversation with summary."""
        self._mode = "conversation"  # VOICE-WIRE: mode transition
        logger.info(f"[MODE] user={self._user_id} → conversation")
