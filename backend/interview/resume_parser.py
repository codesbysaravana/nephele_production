"""
One-time resume parse per user — extracts structured JSON via LLM.
Stores result in parsed_resumes table so it's never re-parsed.
"""

import os
import json
import asyncio  # AUDIT-FIX-1: for to_thread wrapping
from openai import AsyncOpenAI
from dotenv import load_dotenv

from interview.resume_db import ResumeDB

load_dotenv()
_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_db = ResumeDB()

# DECISION: Use LLM for parsing rather than regex/spaCy because resumes are
# wildly inconsistent in format. The structured output ensures clean JSON.
_PARSE_PROMPT = """Extract structured information from this resume text.
Return ONLY valid JSON with these exact keys:
{
  "skills": ["skill1", "skill2", ...],
  "projects": [{"name": "...", "description": "...", "tech": ["..."]}],
  "experience": [{"role": "...", "company": "...", "duration": "...", "highlights": ["..."]}]
}
If a section is missing, return an empty list for that key.
Do not invent information — only extract what's explicitly stated."""


async def parse_and_store(user_id: str, resume_text: str) -> dict:
    """
    Parse resume text into structured JSON and persist.
    Returns the parsed result. Idempotent — if already parsed, returns cached.
    """
    existing = await asyncio.to_thread(_db.get_resume, user_id)  # AUDIT-FIX-1: async SQLite
    if existing:
        return existing

    response = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _PARSE_PROMPT},
            {"role": "user", "content": resume_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw_json = response.choices[0].message.content
    parsed = json.loads(raw_json)

    skills = parsed.get("skills", [])
    projects = parsed.get("projects", [])
    experience = parsed.get("experience", [])

    await asyncio.to_thread(_db.save_parsed_resume, user_id, resume_text, skills, projects, experience)  # AUDIT-FIX-1

    return {"user_id": user_id, "skills": skills, "projects": projects, "experience": experience}
