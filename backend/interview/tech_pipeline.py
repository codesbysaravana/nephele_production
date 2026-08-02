"""
Technical interview pipeline — adaptive questioning via tool-calling.
The LLM decides what to ask next based on resume + prior answers.
"""

import os
import json
import asyncio  # AUDIT-FIX-1: for to_thread wrapping
from openai import AsyncOpenAI
from dotenv import load_dotenv

from ai_services.tts import generate_speech
from interview.resume_db import ResumeDB
from interview.tech_prompts import build_tech_system, SCORING_PROMPT

load_dotenv()
_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_db = ResumeDB()

# DECISION: Two tools — get_next_question lets the LLM reason about what to ask,
# score_answer forces structured evaluation. Both keep the LLM in the loop.
_TOOLS = [
    {"type": "function", "function": {
        "name": "get_next_question",
        "description": "Decide the next interview question based on resume and prior answers.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Skill/project to ask about"},
                "question": {"type": "string", "description": "The question to ask"},
                "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
            },
            "required": ["topic", "question", "difficulty"],
        },
    }},
    {"type": "function", "function": {
        "name": "score_answer",
        "description": "Evaluate the candidate's answer with a 1-5 rubric score.",
        "parameters": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 1, "maximum": 5},
                "notes": {"type": "string", "description": "1-sentence reasoning"},
            },
            "required": ["score", "notes"],
        },
    }},
]


async def generate_question(user_id: str, session_id: str) -> dict | None:
    """
    Ask the LLM to pick the next question. Returns:
    {"topic": ..., "question": ..., "difficulty": ...} or None on failure.
    """
    resume = await asyncio.to_thread(_db.get_resume, user_id)  # AUDIT-FIX-1: async SQLite
    if not resume:
        return None

    prior_qa = await asyncio.to_thread(_db.get_session_qa, session_id)  # AUDIT-FIX-1: async SQLite
    system = build_tech_system(resume, prior_qa)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Pick the next interview question for this candidate."},
    ]

    response = await _client.chat.completions.create(
        model="gpt-4o", messages=messages, tools=_TOOLS, tool_choice="auto",
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        for tc in msg.tool_calls:
            if tc.function.name == "get_next_question":
                args = json.loads(tc.function.arguments)
                return args
    return None


async def score_answer(user_id: str, session_id: str,
                       question: str, answer_text: str) -> dict:
    """
    Score a candidate's answer using LLM rubric. Returns {"score": int, "notes": str}.
    Also persists to fact_interview_qa.
    """
    resume = await asyncio.to_thread(_db.get_resume, user_id)  # AUDIT-FIX-1: async SQLite
    context = f"Question: {question}\nCandidate Answer: {answer_text}"

    messages = [
        {"role": "system", "content": SCORING_PROMPT},
        {"role": "user", "content": context},
    ]

    response = await _client.chat.completions.create(
        model="gpt-4o", messages=messages,
        response_format={"type": "json_object"}, temperature=0,
    )

    result = json.loads(response.choices[0].message.content)
    score = max(1, min(5, int(result.get("score", 3))))
    notes = result.get("notes", "")

    await asyncio.to_thread(_db.log_qa, user_id, session_id, question, answer_text, score, notes)  # AUDIT-FIX-1
    return {"score": score, "notes": notes}


async def speak_question(question_text: str):
    """Generate TTS audio for the interview question. Returns bytes."""
    return await generate_speech(question_text)
