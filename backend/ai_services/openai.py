"""
Main Voice Pipeline — Nephele's core conversational brain.
Handles: streaming LLM, tool calling (memory, routing, SQL), TTS dispatch.
"""

import os
import json
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI

from ai_services.tts import generate_speech
from ai_services.streaming import stream_llm_response, synthesize_tool_result
from db.query import execute_safe_query

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Persistent memory backed by SQLite
_MEMORY_DB = Path(__file__).parent.parent / "attendance.db"
_mem_conn = sqlite3.connect(str(_MEMORY_DB))
_mem_conn.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT, fact TEXT NOT NULL)")
_mem_conn.commit()

conversation_history = []
saved_facts = [row[0] for row in _mem_conn.execute("SELECT fact FROM memory").fetchall()]

SYSTEM_PROMPT = """
You are Nephele, a fast, friendly AI companion created by the PeP Cloud students.
Respond conversationally in no more than 3 short sentences. Give the direct answer first, avoid filler, and only expand if the user explicitly asks. Speak naturally as if talking to a friend.
If someone asks who created you, say you were built by the PeP Cloud students. Never bring it up unless it's relevant or you're asked.

You have access to a PostgreSQL data warehouse with these tables:
- dim_users: customer_id (TEXT PK), customer_name (TEXT), total_spent (NUMERIC), spending_rank (INTEGER)
- fact_sales: transaction_id (TEXT PK), customer_id (TEXT FK), amount (NUMERIC), sale_date (DATE), running_daily_revenue (NUMERIC)

When the user asks data questions, use the query_database tool with a SELECT query. Never run INSERT/UPDATE/DELETE/DROP/ALTER.
When the user asks to see analytics or the dashboard, use the show_dashboard tool.
"""

tools = [
    {"type": "function", "function": {
        "name": "save_memory",
        "description": "Save an important fact about the user to long-term memory.",
        "parameters": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}
    }},
    {"type": "function", "function": {
        "name": "trigger_attendance_mode",
        "description": "Trigger this tool if the user asks to take attendance or scan a QR code.",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "query_database",
        "description": "Execute a read-only SELECT query against the PostgreSQL data warehouse.",
        "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}
    }},
    {"type": "function", "function": {
        "name": "show_dashboard",
        "description": "Show the analytics dashboard with live charts.",
        "parameters": {"type": "object", "properties": {}}
    }},
]


def _append_history(msg: dict):
    conversation_history.append(msg)
    if len(conversation_history) > 10:
        conversation_history.pop(0)


async def process_voice_pipeline(user_text: str):
    global conversation_history, saved_facts

    if not user_text:
        return

    _append_history({"role": "user", "content": user_text})

    # Inject long-term memory into the system prompt
    sys_prompt = SYSTEM_PROMPT
    if saved_facts:
        sys_prompt += "\n\nFacts you've saved:\n" + "\n".join(f"- {f}" for f in saved_facts)

    messages = [{"role": "system", "content": sys_prompt}] + conversation_history

    # Stream LLM response — yields audio, final item is result tuple
    full_text = ""
    tool_name = ""
    tool_args = ""

    async for item in stream_llm_response(client, messages, tools):
        if isinstance(item, tuple) and item[0] == "__result__":
            _, full_text, tool_name, tool_args = item
        else:
            yield item

    # Handle tool calls
    if tool_name:
        async for audio in _handle_tool(tool_name, tool_args):
            if isinstance(audio, tuple) and audio[0] == "__result__":
                full_text = audio[1]
            else:
                yield audio

    if full_text:
        _append_history({"role": "assistant", "content": full_text})


async def _handle_tool(tool_name: str, tool_args_raw: str):
    """Dispatch tool calls. Yields audio bytes or JSON route commands."""

    if tool_name == "save_memory":
        args = json.loads(tool_args_raw)
        fact = args.get("fact", "")
        if fact:
            saved_facts.append(fact)
            _mem_conn.execute("INSERT INTO memory (fact) VALUES (?)", (fact,))
            _mem_conn.commit()
            ack = "Got it, I'll commit that to memory."
            audio = await generate_speech(ack)
            if audio:
                yield audio
            yield ("__result__", ack)

    elif tool_name == "trigger_attendance_mode":
        yield json.dumps({"command": "route", "path": "#/attendance"})
        yield ("__result__", "")

    elif tool_name == "show_dashboard":
        yield json.dumps({"command": "route", "path": "#/dashboard"})
        yield ("__result__", "")

    elif tool_name == "query_database":
        args = json.loads(tool_args_raw)
        sql = args.get("sql", "")
        result = execute_safe_query(sql)

        # Append tool call + result to history for synthesis
        _append_history({"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_db", "type": "function", "function": {"name": "query_database", "arguments": tool_args_raw}}
        ]})
        _append_history({"role": "tool", "tool_call_id": "call_db", "content": result})

        # Second LLM call to synthesize a spoken answer
        full_synth = ""
        async for item in synthesize_tool_result(client, SYSTEM_PROMPT, conversation_history):
            if isinstance(item, tuple) and item[0] == "__result__":
                full_synth = item[1]
            else:
                yield item
        yield ("__result__", full_synth)
