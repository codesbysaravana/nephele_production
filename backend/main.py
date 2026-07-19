import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
import websockets
import json

from ai_services.openai import process_voice_pipeline
from ai_services.dashboard_brain import process_dashboard_voice
from attendance_db import AttendanceDB
from ml.router import router as ml_router
from analytics_router import router as analytics_router

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="Nephele Backend")
db = AttendanceDB()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(ml_router)
app.include_router(analytics_router)

DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&endpointing=300"
API_KEY = os.getenv("DEEPGRAM_API_KEY")


# ============================================================
# REST Endpoints
# ============================================================

@app.get("/")
async def welcome():
    return {"status": "Nephele Backend Welcome"}


@app.get("/health")
async def health_check():
    return {"status": "Nephele is awake and listening!"}


@app.get("/api/attendance")
async def get_all_attendance():
    records = db.get_all_scans()
    return {"status": "success", "data": records}


@app.post("/api/attendance")
async def take_attendance(request: Request):
    data = await request.json()
    student_id = data.get("student_id", "UNKNOWN")
    db.log_scan(student_id=student_id, raw_payload=data)
    logger.info(f"Attendance Logged: {student_id}")
    return {"status": "success", "message": "Attendance saved to SQLite!"}


# ============================================================
# Shared Deepgram WebSocket Session
# ============================================================

async def _deepgram_session(websocket: WebSocket, brain_fn, label: str):
    """
    Reusable STT session: connects browser mic to Deepgram, pipes
    final transcripts into brain_fn, sends audio/commands back to browser.
    """
    await websocket.accept()
    logger.info(f"[{label}] Connected")

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with websockets.connect(DEEPGRAM_URL, additional_headers=headers) as dg:

            async def mic_to_deepgram():
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg["type"] == "websocket.disconnect":
                            break
                        if "bytes" in msg and msg["bytes"]:
                            await dg.send(msg["bytes"])
                except Exception as e:
                    logger.error(f"[{label}] mic->dg: {e}")

            async def deepgram_to_brain():
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
                                logger.info(f"[{label}] Transcript: {text}")
                                asyncio.create_task(_run_brain(websocket, brain_fn, text, label))
                except Exception as e:
                    logger.error(f"[{label}] dg->brain: {e}")

            async def keepalive():
                try:
                    while True:
                        await asyncio.sleep(8)
                        await dg.send(json.dumps({"type": "KeepAlive"}))
                except Exception:
                    pass

            await asyncio.gather(mic_to_deepgram(), deepgram_to_brain(), keepalive())

    except WebSocketDisconnect:
        logger.info(f"[{label}] Disconnected")
    except Exception as e:
        logger.error(f"[{label}] Error: {e}")


async def _run_brain(websocket: WebSocket, brain_fn, text: str, label: str):
    """Run a brain function and send its output (audio bytes or JSON commands) to the client."""
    try:
        async for chunk in brain_fn(text):
            if isinstance(chunk, tuple):
                continue  # internal metadata, not for the client
            elif isinstance(chunk, str):
                await websocket.send_text(chunk)
                logger.info(f"[{label}] Sent command: {chunk}")
            else:
                await websocket.send_bytes(chunk)
    except Exception as e:
        logger.error(f"[{label}] Brain error: {e}")


# ============================================================
# WebSocket Endpoints
# ============================================================

@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    await _deepgram_session(websocket, process_voice_pipeline, "VOICE")


@app.websocket("/ws/dashboard-voice")
async def dashboard_voice_endpoint(websocket: WebSocket):
    await _deepgram_session(websocket, process_dashboard_voice, "DASHBOARD")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
