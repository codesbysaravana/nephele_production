"""
Dashboard Voice Brain — Isolated analytics conversation loop.
Completely separate from the main voice pipeline.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI

from ai_services.tts import generate_speech
from ai_services.streaming import stream_llm_response, synthesize_tool_result
from db.query import execute_safe_query
from ml.predict import predict as ml_predict

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

dashboard_history = []

SYSTEM_PROMPT = """
You are Nephele Analytics, a data analyst AI on the analytics dashboard page.

PostgreSQL tables available:
- dim_users: customer_id, customer_name, total_spent, spending_rank
- fact_sales: transaction_id, customer_id, amount, sale_date, running_daily_revenue

Dashboard shows: Revenue by Day, Top Customers, Spending Distribution, Cumulative Revenue, ML Attendance Forecast.

Tools: query_database (SQL), predict_attendance (ML forecast).
Keep answers to 2-3 sentences. Speak like a friendly analyst. Only SELECT queries allowed.
"""

tools = [
    {"type": "function", "function": {
        "name": "query_database",
        "description": "Run a read-only SELECT query against the data warehouse.",
        "parameters": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}
    }},
    {"type": "function", "function": {
        "name": "predict_attendance",
        "description": "Predict attendance for a specific day. Use for forecasts, weak days, or skip predictions.",
        "parameters": {"type": "object", "properties": {
            "day_of_week": {"type": "integer", "description": "0=Mon, 6=Sun"},
            "hour": {"type": "integer"},
            "historical_rate": {"type": "number", "description": "0.0-1.0, use 0.75 if unknown"}
        }, "required": ["day_of_week", "hour", "historical_rate"]}
    }},
]


def _append_history(msg: dict):
    dashboard_history.append(msg)
    if len(dashboard_history) > 10:
        dashboard_history.pop(0)


async def process_dashboard_voice(user_text: str):
    global dashboard_history

    if not user_text:
        return

    _append_history({"role": "user", "content": user_text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + dashboard_history

    full_text = ""
    tool_name = ""
    tool_args = ""

    async for item in stream_llm_response(client, messages, tools):
        if isinstance(item, tuple) and item[0] == "__result__":
            _, full_text, tool_name, tool_args = item
        else:
            yield item

    if tool_name:
        async for audio in _handle_tool(tool_name, tool_args):
            if isinstance(audio, tuple) and audio[0] == "__result__":
                full_text = audio[1]
            else:
                yield audio

    if full_text:
        _append_history({"role": "assistant", "content": full_text})


async def _handle_tool(tool_name: str, tool_args_raw: str):
    """Dispatch dashboard-specific tools."""

    if tool_name == "query_database":
        args = json.loads(tool_args_raw)
        result = execute_safe_query(args.get("sql", ""))

        _append_history({"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_d", "type": "function", "function": {"name": "query_database", "arguments": tool_args_raw}}
        ]})
        _append_history({"role": "tool", "tool_call_id": "call_d", "content": result})

        full_synth = ""
        async for item in synthesize_tool_result(client, SYSTEM_PROMPT, dashboard_history):
            if isinstance(item, tuple) and item[0] == "__result__":
                full_synth = item[1]
            else:
                yield item
        yield ("__result__", full_synth)

    elif tool_name == "predict_attendance":
        args = json.loads(tool_args_raw)
        week_number = datetime.now().isocalendar()[1] % 52
        result = ml_predict(
            day_of_week=args.get("day_of_week", 0),
            hour=args.get("hour", 10),
            week_number=week_number,
            historical_rate=args.get("historical_rate", 0.75),
        )

        _append_history({"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_m", "type": "function", "function": {"name": "predict_attendance", "arguments": tool_args_raw}}
        ]})
        _append_history({"role": "tool", "tool_call_id": "call_m", "content": json.dumps(result)})

        full_synth = ""
        async for item in synthesize_tool_result(client, SYSTEM_PROMPT, dashboard_history):
            if isinstance(item, tuple) and item[0] == "__result__":
                full_synth = item[1]
            else:
                yield item
        yield ("__result__", full_synth)
