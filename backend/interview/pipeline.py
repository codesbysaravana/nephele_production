"""
Interview voice pipeline — per-user LLM streaming with tool-calling.
Reuses the shared streaming/TTS utilities from ai_services/.
"""

import os
import json
import asyncio  # AUDIT-FIX-1: for to_thread wrapping
from openai import AsyncOpenAI
from dotenv import load_dotenv

from ai_services.streaming import stream_llm_response
from ai_services.tts import generate_speech
from interview.memory import UserMemory
from interview.prompts import build_system_message

load_dotenv()
_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_memory_store = UserMemory()

# DECISION: Only one tool for now (save_memory). More tools added in later modules.
_TOOLS = [
    {"type": "function", "function": {
        "name": "save_memory",
        "description": "Save an important fact about this candidate to long-term memory.",
        "parameters": {
            "type": "object",
            "properties": {"fact": {"type": "string"}},
            "required": ["fact"],
        },
    }},
]


async def run_interview_turn(user_text: str, user_id: str, history: list):
    """
    Process one user turn through the interview pipeline.
    Yields audio bytes (and JSON commands) to send over WebSocket.
    Returns nothing — caller reads the generator.

    `history` is mutated in-place (appended to) so the session object
    stays in sync without extra bookkeeping.
    """
    if not user_text:
        return

    history.append({"role": "user", "content": user_text})

    facts = await asyncio.to_thread(_memory_store.get_facts, user_id)  # AUDIT-FIX-1: async SQLite
    system_msg = build_system_message(facts)
    messages = [{"role": "system", "content": system_msg}] + history

    full_text = ""
    tool_name = ""
    tool_args = ""

    async for item in stream_llm_response(_client, messages, _TOOLS):
        if isinstance(item, tuple) and item[0] == "__result__":
            _, full_text, tool_name, tool_args = item
        else:
            yield item

    # Handle tool calls
    if tool_name:
        async for audio in _handle_tool(tool_name, tool_args, user_id):
            if isinstance(audio, tuple) and audio[0] == "__result__":
                full_text = audio[1]
            else:
                yield audio

    if full_text:
        history.append({"role": "assistant", "content": full_text})


async def _handle_tool(tool_name: str, tool_args_raw: str, user_id: str):
    """Dispatch tool calls. Currently only save_memory is supported."""
    if tool_name == "save_memory":
        args = json.loads(tool_args_raw)
        fact = args.get("fact", "")
        if fact:
            await asyncio.to_thread(_memory_store.save_fact, user_id, fact)  # AUDIT-FIX-1: async SQLite
            ack = "Got it, I'll remember that."
            audio = await generate_speech(ack)
            if audio:
                yield audio
            yield ("__result__", ack)
