"""Streaming voice protocol. Each connection owns and closes its provider clients.

AssemblyAI Universal-Streaming STT port (was Deepgram nova-2 via deepgram-sdk v7).
Why: Deepgram's streaming endpoint stopped returning transcripts for traffic
from Render and Railway IPs (~Oct 16) while identical traffic works elsewhere;
the vendor-side issue is unresolved, so STT moves to AssemblyAI.
Changes vs the Deepgram version:
- STT leg is a plain websockets connection to AssemblyAI's v3 streaming API
  (Begin / SpeechStarted / Turn / Termination messages). No new dependency:
  the project already uses websockets.
- One Turn with end_of_turn=true carries the whole finalized utterance, so the
  Deepgram is_final/speech_final stitching (pending list) is gone.
- No KeepAlive task: AssemblyAI has no ~10s idle timeout (sessions can stay
  open for hours; our own 15-minute session deadline still applies).
- The frontend WebSocket protocol is unchanged: same /ws/voice messages in
  both directions, same 16 kHz linear16 audio frames.
- TTS still uses Deepgram aura-asteria-en (HTTPS POST, unaffected by the
  streaming issue); LLM still uses OpenAI gpt-4o-mini.
"""
import asyncio
import json
import logging
import os
from contextlib import suppress

import httpx
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI

router = APIRouter()
logger = logging.getLogger(__name__)
STT_URL = "wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&encoding=pcm_s16le"
TTS_URL = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&sample_rate=24000&container=none"
SYSTEM_PROMPT = (
    "You are Nephele, a college placement companion. Keep answers brief (1-3 sentences) "
    "because they are spoken aloud. If the user says goodbye or asks to hang up, "
    "use the close_connection tool. You were built by The Cloud Pep Students, "
    "main Tech Leads Saravana and Joshua."
)
TOOLS = [{"type": "function", "function": {
    "name": "close_connection", "description": "Hang up when the user says goodbye or asks to end the call.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}}]


async def cancel_task(task):
    if task is not None:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task


def trim_history(history):
    """Keep the system prompt and at most ten complete user/assistant turns."""
    while len(history) > 21:
        del history[1]
    while len(history) > 1 and history[1]["role"] != "user":
        del history[1]


async def stream_tts_to_ws(sentence, websocket, cancelled, http_client, api_key):
    if cancelled.is_set():
        return
    async with http_client.stream(
        "POST", TTS_URL,
        headers={"Authorization": f"Token {api_key}"}, json={"text": sentence},
    ) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes(4096):
            if cancelled.is_set():
                return
            await asyncio.wait_for(websocket.send_bytes(chunk), timeout=5)


async def generate_llm_and_tts(
    transcript, websocket, conversation_history, cancelled, history_lock,
    openai_client, http_client, api_key,
):
    """Cancellation reaches both network streams, including while awaiting headers."""
    if cancelled.is_set():
        return
    async with history_lock:
        messages = [dict(message) for message in conversation_history]
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini", messages=messages, tools=TOOLS, stream=True,
    )
    sentences = asyncio.Queue(maxsize=8)

    async def speak():
        while True:
            sentence = await sentences.get()
            if sentence is None:
                return
            await stream_tts_to_ws(sentence, websocket, cancelled, http_client, api_key)

    speaker = asyncio.create_task(speak())

    async def enqueue(sentence):
        # A failed TTS consumer must not leave the producer blocked on a full queue.
        put = asyncio.create_task(sentences.put(sentence))
        try:
            done, _ = await asyncio.wait([put, speaker], return_when=asyncio.FIRST_COMPLETED)
            if speaker in done:
                await speaker
                if sentence is not None:
                    raise RuntimeError("Speech stream stopped")
            await put
        finally:
            await cancel_task(put)

    buffer = ""
    answer = ""
    close_requested = False
    try:
        async for chunk in response:
            if cancelled.is_set():
                return
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            for call in delta.tool_calls or []:
                if call.function and call.function.name == "close_connection":
                    close_requested = True
            if delta.content:
                answer += delta.content
                buffer += delta.content
                await websocket.send_json({"type": "text", "content": delta.content})
                boundaries = [buffer.rfind(p) for p in (". ", "? ", "! ", ".\n", "?\n", "!\n")]
                boundary = max(boundaries)
                if boundary >= 0:
                    sentence, buffer = buffer[:boundary + 1].strip(), buffer[boundary + 1:]
                    if sentence:
                        await enqueue(sentence)
        if buffer.strip():
            await enqueue(buffer.strip())
        await enqueue(None)
        await speaker
        if cancelled.is_set():
            return
        if answer:
            async with history_lock:
                conversation_history.append({"role": "assistant", "content": answer})
                trim_history(conversation_history)
        await websocket.send_json({"type": "audio_complete"})
        if close_requested:
            await websocket.send_json({"type": "close"})
    finally:
        await cancel_task(speaker)
        await response.close()


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    allowed = [value.strip() for value in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if value.strip()]
    if websocket.headers.get("origin") not in allowed:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    openai_key = os.getenv("OPENAI_API_KEY")
    assemblyai_key = os.getenv("ASSEMBLYAI_API_KEY")
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")  # TTS only
    if not openai_key or not assemblyai_key or not deepgram_key:
        await websocket.send_json({"type": "error", "message": "Voice service is not configured. Please contact the site owner."})
        await websocket.close(code=1011)
        return

    current_task = None
    current_cancel = asyncio.Event()
    turn_lock = asyncio.Lock()
    history_lock = asyncio.Lock()
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    listener = None
    stt_connection = None

    async def interrupt():
        nonlocal current_task
        current_cancel.set()
        await cancel_task(current_task)
        current_task = None

    try:
        async with AsyncOpenAI(api_key=openai_key, timeout=30.0) as llm, \
                   httpx.AsyncClient(timeout=20.0) as http:
            async with websockets.connect(
                STT_URL, additional_headers={"Authorization": assemblyai_key},
                max_size=2**22,
            ) as stt_ws:
                stt_connection = stt_ws

                async def run_pipeline(sentence, cancel):
                    try:
                        await generate_llm_and_tts(sentence, websocket, history, cancel, history_lock, llm, http, deepgram_key)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("Voice response failed")
                        with suppress(Exception):
                            await websocket.send_json({"type": "error", "message": "The voice service had a problem. Please try again."})
                            await websocket.close(code=1011)

                async def handle_message(message):
                    nonlocal current_cancel, current_task
                    try:
                        msg_type = message.get("type")
                        if msg_type == "Begin":
                            logger.info("AssemblyAI stream opened, session_id=%s", message.get("id"))
                            return
                        if msg_type == "Error":
                            logger.error("AssemblyAI stream error: %s", message.get("error"))
                            with suppress(Exception):
                                await websocket.send_json({"type": "error", "message": "Speech recognition disconnected. Please reconnect."})
                                await websocket.close(code=1011)
                            return
                        if msg_type == "SpeechStarted":
                            async with turn_lock:
                                await interrupt()
                                await websocket.send_json({"type": "interrupted"})
                            return
                        if msg_type == "Termination":
                            logger.info("AssemblyAI stream terminated: %s", message.get("audio_duration_seconds"))
                            return
                        if msg_type != "Turn":
                            logger.warning("Unhandled AssemblyAI message: %r", message)
                            return
                        # Interim turns stream partial text; the end-of-turn Turn
                        # carries the whole finalized utterance.
                        if not message.get("end_of_turn"):
                            return
                        sentence = (message.get("transcript") or "").strip()
                        if not sentence:
                            return
                        async with turn_lock:
                            sentence = sentence[:4000]
                            await interrupt()
                            async with history_lock:
                                history.append({"role": "user", "content": sentence})
                                trim_history(history)
                            await websocket.send_json({"type": "user_text", "content": sentence})
                            current_cancel = asyncio.Event()
                            current_task = asyncio.create_task(run_pipeline(sentence, current_cancel))
                    except Exception:
                        # Never let one bad message kill the session silently.
                        logger.exception("Failed to handle AssemblyAI message")

                async def listen():
                    async for raw in stt_ws:
                        await handle_message(json.loads(raw))

                listener = asyncio.create_task(listen())
                await websocket.send_json({"type": "ready"})
                # Bounded session length limits abandoned connections, not provider usage quotas.
                deadline = asyncio.get_running_loop().time() + 15 * 60
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    data = await asyncio.wait_for(websocket.receive_bytes(), timeout=remaining)
                    if len(data) > 65536:
                        await websocket.close(code=1009)
                        break
                    await stt_ws.send(data)
    except WebSocketDisconnect:
        pass
    except asyncio.TimeoutError:
        with suppress(Exception):
            await websocket.send_json({"type": "error", "message": "This session has ended. Start a new call to continue."})
            await websocket.close(code=1000)
    except Exception:
        logger.exception("Voice connection failed")
        with suppress(Exception):
            await websocket.send_json({"type": "error", "message": "Could not connect to the voice service. Please try again."})
            await websocket.close(code=1011)
    finally:
        if stt_connection is not None:
            # Ask AssemblyAI to finalize the session before the socket closes.
            with suppress(Exception):
                await stt_connection.send(json.dumps({"type": "Terminate"}))
        await interrupt()
        await cancel_task(listener)
