"""Streaming voice protocol. Each connection owns and closes its provider clients."""
import asyncio
import logging
import os
from contextlib import suppress

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from openai import AsyncOpenAI

router = APIRouter()
logger = logging.getLogger(__name__)
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
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    if not openai_key or not deepgram_key:
        await websocket.send_json({"type": "error", "message": "Voice service is not configured. Please contact the site owner."})
        await websocket.close(code=1011)
        return

    current_task = None
    current_cancel = asyncio.Event()
    turn_lock = asyncio.Lock()
    history_lock = asyncio.Lock()
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    pending = []
    dg_connection = None

    async def interrupt():
        nonlocal current_task
        current_cancel.set()
        await cancel_task(current_task)
        current_task = None

    try:
        async with AsyncOpenAI(api_key=openai_key, timeout=30.0) as llm, httpx.AsyncClient(timeout=20.0) as http:
            try:
                dg_connection = DeepgramClient(deepgram_key).listen.asyncwebsocket.v("1")

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

                async def on_speech_started(*args, **kwargs):
                    async with turn_lock:
                        await interrupt()
                        await websocket.send_json({"type": "interrupted"})

                async def on_message(*args, result, **kwargs):
                    nonlocal current_cancel, current_task
                    alternatives = result.channel.alternatives
                    sentence = alternatives[0].transcript.strip() if alternatives else ""
                    async with turn_lock:
                        if sentence and result.is_final:
                            pending.append(sentence)
                        # Deepgram is_final ends a segment; speech_final ends the utterance.
                        if not result.speech_final or not pending:
                            return
                        sentence = " ".join(pending)[:4000]
                        pending.clear()
                        await interrupt()
                        async with history_lock:
                            history.append({"role": "user", "content": sentence})
                            trim_history(history)
                        await websocket.send_json({"type": "user_text", "content": sentence})
                        current_cancel = asyncio.Event()
                        current_task = asyncio.create_task(run_pipeline(sentence, current_cancel))

                async def on_error(*args, **kwargs):
                    logger.warning("Speech recognition stream failed")
                    with suppress(Exception):
                        await websocket.send_json({"type": "error", "message": "Speech recognition disconnected. Please reconnect."})
                        await websocket.close(code=1011)

                dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
                dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
                dg_connection.on(LiveTranscriptionEvents.Error, on_error)
                started = await dg_connection.start(LiveOptions(
                    model="nova-2", language="en-US", smart_format=True,
                    interim_results=True, vad_events=True, encoding="linear16",
                    sample_rate=16000, channels=1, endpointing=750,
                ))
                if not started:
                    raise RuntimeError("Speech recognition did not start")
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
                    await dg_connection.send(data)
            finally:
                await interrupt()
                if dg_connection is not None:
                    with suppress(Exception):
                        await asyncio.wait_for(dg_connection.finish(), timeout=5)
                    dg_connection = None
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
        await interrupt()
        if dg_connection is not None:
            with suppress(Exception):
                await asyncio.wait_for(dg_connection.finish(), timeout=5)
