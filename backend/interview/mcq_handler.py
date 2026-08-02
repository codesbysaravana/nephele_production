"""
Handles text-frame commands for the MCQ round over the WebSocket.
Called from the router when a text frame arrives during an interview session.
"""

import json
import logging
from fastapi import WebSocket

from interview.mcq_engine import McqEngine

logger = logging.getLogger(__name__)


async def handle_mcq_command(raw_text: str, mcq_engine: McqEngine,
                             ws: WebSocket, user_id: str, session_id: str) -> bool:
    """
    Parse and dispatch an MCQ command. Returns True if handled, False otherwise.
    Unrecognized commands are not MCQ-related and should be ignored here.
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return False

    action = data.get("action", "")

    if action == "start_mcq":
        # DECISION: Allow optional topic filter. None = mixed from all topics.
        topic = data.get("topic")
        await mcq_engine.start(topic)
        return True

    if action == "answer_mcq":
        answer = data.get("answer", "")
        await mcq_engine.handle_answer(answer)
        return True

    if action == "skip_mcq":
        await mcq_engine.handle_skip()
        return True

    return False
