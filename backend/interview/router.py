"""WebSocket /ws/interview — fully voice-driven interview pipeline."""

import os
import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets
from dotenv import load_dotenv

from interview.db import InterviewDB
from interview.mode_router import ModeRouter
from interview.proctor_handler import handle_proctor_command  # VOICE-WIRE: proctor stays as JSON

load_dotenv()
logger = logging.getLogger(__name__)
router = APIRouter()

_db = InterviewDB()

DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&endpointing=300"
_DG_KEY = os.getenv("DEEPGRAM_API_KEY")


@router.websocket("/ws/interview")
async def interview_ws(websocket: WebSocket):
    """Handshake: client sends {user_id, name}. Then all audio — fully voice-driven."""
    await websocket.accept()

    try:
        init_raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        init = json.loads(init_raw)
        user_id = init["user_id"]
        name = init.get("name", "Anonymous")
    except (asyncio.TimeoutError, KeyError, json.JSONDecodeError) as e:
        logger.error(f"[INTERVIEW] Bad handshake: {e}")
        await websocket.close(code=4000, reason="Send {user_id, name} as first frame")
        return

    await asyncio.to_thread(_db.get_or_create_user, user_id, name)  # AUDIT-FIX-1
    session_id = await asyncio.to_thread(_db.create_session, user_id)  # AUDIT-FIX-1

    prev_session = await asyncio.to_thread(_get_previous_session, user_id, session_id)
    history = await asyncio.to_thread(_db.get_session_messages, prev_session) if prev_session else []
    logger.info(f"[INTERVIEW] User={user_id} Session={session_id} History={len(history)} msgs")

    # VOICE-WIRE: ModeRouter handles all STT transcript routing by session state.
    mode = ModeRouter(user_id, session_id, websocket, history)

    headers = {"Authorization": f"Token {_DG_KEY}"}

    try:
        async with websockets.connect(DEEPGRAM_URL, additional_headers=headers) as dg:
            async def client_to_server():
                """Binary→Deepgram. Text→proctor events only (no UI MCQ/tech frames)."""
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg["type"] == "websocket.disconnect":
                            break
                        # VOICE-WIRE: Text frames only for proctor events (client-side JS)
                        if "text" in msg and msg["text"]:
                            await handle_proctor_command(
                                msg["text"], websocket, user_id, session_id
                            )
                        elif "bytes" in msg and msg["bytes"]:
                            await dg.send(msg["bytes"])
                except Exception as e:
                    logger.error(f"[INTERVIEW] client->server: {e}")

            async def deepgram_to_brain():
                """STT transcripts → ModeRouter for voice-driven dispatch."""
                try:
                    while True:
                        raw = await dg.recv()
                        resp = json.loads(raw)
                        if resp.get("type") != "Results":
                            continue
                        if not resp.get("speech_final"):
                            continue
                        alts = resp.get("channel", {}).get("alternatives", [])
                        if alts:
                            text = alts[0].get("transcript", "")
                            if text:
                                # VOICE-WIRE: Fire-and-forget so Deepgram loop stays unblocked
                                logger.info(f"[INTERVIEW:{mode.mode}] {text}")
                                asyncio.create_task(_persist_and_route(
                                    mode, text, session_id
                                ))
                except Exception as e:
                    logger.error(f"[INTERVIEW] dg->brain: {e}")

            async def keepalive():
                try:
                    while True:
                        await asyncio.sleep(8)
                        await dg.send(json.dumps({"type": "KeepAlive"}))
                except Exception: pass

            await asyncio.gather(client_to_server(), deepgram_to_brain(), keepalive())

    except WebSocketDisconnect:
        logger.info(f"[INTERVIEW] Disconnected user={user_id}")
    except Exception as e:
        logger.error(f"[INTERVIEW] Error: {e}")


async def _persist_and_route(mode: ModeRouter, text: str, session_id: str):
    """Route to brain immediately, persist in background for speed."""
    asyncio.create_task(asyncio.to_thread(_db.save_message, session_id, "user", text))  # background persist
    await mode.route_transcript(text)


def _get_previous_session(user_id: str, current_session_id: str) -> str | None:
    with _db._connect() as conn:
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE user_id = ? ORDER BY started_at DESC LIMIT 2",
            (user_id,),
        ).fetchall()
        for row in rows:
            if row["session_id"] != current_session_id:
                return row["session_id"]
    return None
