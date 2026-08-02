"""
Handles text-frame commands for the technical interview round.
Actions: submit_resume, next_question, submit_answer, end_tech_round.
"""

import json
import logging
from fastapi import WebSocket

from interview.resume_parser import parse_and_store
from interview.tech_pipeline import generate_question, score_answer, speak_question

logger = logging.getLogger(__name__)


async def handle_tech_command(raw_text: str, ws: WebSocket,
                              user_id: str, session_id: str) -> bool:
    """
    Parse and dispatch a tech-round command.
    Returns True if handled, False if not a tech command.
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        return False

    action = data.get("action", "")

    if action == "submit_resume":
        return await _handle_resume(data, ws, user_id)

    if action == "next_question":
        return await _handle_next_question(ws, user_id, session_id)

    if action == "submit_answer":
        return await _handle_answer(data, ws, user_id, session_id)

    return False


async def _handle_resume(data: dict, ws: WebSocket, user_id: str) -> bool:
    """Parse resume text and confirm to client."""
    resume_text = data.get("resume_text", "")
    if not resume_text:
        await ws.send_text(json.dumps({
            "type": "tech_error", "message": "resume_text is required"
        }))
        return True

    parsed = await parse_and_store(user_id, resume_text)
    await ws.send_text(json.dumps({
        "type": "resume_parsed",
        "skills": parsed["skills"],
        "projects_count": len(parsed["projects"]),
        "experience_count": len(parsed["experience"]),
    }))
    logger.info(f"[TECH] Resume parsed for user={user_id}, skills={len(parsed['skills'])}")
    return True


async def _handle_next_question(ws: WebSocket, user_id: str, session_id: str) -> bool:
    """Generate and send the next adaptive question."""
    q = await generate_question(user_id, session_id)
    if not q:
        await ws.send_text(json.dumps({
            "type": "tech_error", "message": "No resume on file. Submit resume first."
        }))
        return True

    # Send question as JSON
    await ws.send_text(json.dumps({
        "type": "tech_question",
        "topic": q["topic"],
        "question": q["question"],
        "difficulty": q["difficulty"],
    }))

    # Also speak the question via TTS
    audio = await speak_question(q["question"])
    if audio:
        await ws.send_bytes(audio)

    return True


async def _handle_answer(data: dict, ws: WebSocket,
                         user_id: str, session_id: str) -> bool:
    """Score the candidate's answer and send feedback."""
    question = data.get("question", "")
    answer_text = data.get("answer_text", "")
    if not question or not answer_text:
        await ws.send_text(json.dumps({
            "type": "tech_error", "message": "question and answer_text required"
        }))
        return True

    result = await score_answer(user_id, session_id, question, answer_text)

    # DECISION: Don't reveal numeric score to candidate — just acknowledge.
    # Score is logged internally for readiness ML.
    await ws.send_text(json.dumps({
        "type": "tech_answer_received",
        "question": question,
        "scored": True,
    }))

    return True
