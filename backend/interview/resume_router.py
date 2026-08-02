"""
REST endpoint for resume upload and parsing.
POST /api/resume/upload — accepts PDF or text, parses via LLM, stores result.
"""

import asyncio
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from interview.resume_extract import extract_text_from_file
from interview.resume_parser import parse_and_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resume", tags=["resume"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), user_id: str = Form(...)):
    """
    Upload a PDF or text resume. Extracts text, parses via LLM,
    stores structured result in parsed_resumes table.
    """
    # Validate by extension — content_type varies wildly across browsers
    filename = file.filename or ""
    if not filename.lower().endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, f"Only PDF or plain text files. Got: {filename}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large. Max 5MB.")
    if not content:
        raise HTTPException(400, "Empty file.")

    # Extract raw text from file bytes
    try:
        raw_text = await asyncio.to_thread(extract_text_from_file, content, filename)
    except ValueError as e:
        raise HTTPException(422, str(e))

    if not raw_text.strip():
        raise HTTPException(422, "Could not extract any text from the file.")

    # Parse via LLM and store
    parsed = await parse_and_store(user_id, raw_text)

    logger.info(f"[RESUME] Uploaded for user={user_id}, skills={len(parsed['skills'])}")
    return {
        "status": "success",
        "data": {
            "skills": parsed["skills"],
            "projects": parsed["projects"],
            "experience": parsed["experience"],
        },
    }
