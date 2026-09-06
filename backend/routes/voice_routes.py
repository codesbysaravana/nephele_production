import os
import asyncio
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
deepgram = DeepgramClient(DEEPGRAM_API_KEY)

_tts_http_client = httpx.AsyncClient(timeout=15.0)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "close_connection",
            "description": "Close the WebSocket connection and hang up the voice call. Use this when the user says 'close the connection', 'hang up', or 'goodbye'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

TTS_URL = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&sample_rate=24000"
TTS_HEADERS = {
    "Authorization": f"Token {DEEPGRAM_API_KEY}",
    "Content-Type": "application/json"
}


async def stream_tts_to_ws(sentence: str, websocket: WebSocket, cancelled: asyncio.Event):
    """Stream a single sentence's TTS audio to the client. Stops early if cancelled."""
    try:
        async with _tts_http_client.stream("POST", TTS_URL, headers=TTS_HEADERS, json={"text": sentence}) as r:
            if r.status_code == 200:
                async for chunk in r.aiter_bytes(4096):
                    if cancelled.is_set():
                        return
                    await websocket.send_bytes(chunk)
            else:
                body = await r.aread()
                print(f"TTS Error: {r.status_code} {body.decode()}")
    except Exception as e:
        print(f"TTS Network Error: {e}")


async def generate_llm_and_tts(
    transcript: str,
    websocket: WebSocket,
    conversation_history: list,
    cancelled: asyncio.Event,
):
    """Stream LLM response and pipe sentences to TTS concurrently."""
    if transcript:
        print(f"User: {transcript}")

    if cancelled.is_set():
        return

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history,
        tools=TOOLS,
        stream=True,
    )

    # TTS worker with prefetch: allows next sentence to start fetching
    # while current sentence is still streaming
    sentence_queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def tts_worker():
        while True:
            sentence = await sentence_queue.get()
            if sentence is None:
                break
            if cancelled.is_set():
                sentence_queue.task_done()
                break
            await stream_tts_to_ws(sentence, websocket, cancelled)
            sentence_queue.task_done()

    tts_task = asyncio.create_task(tts_worker())

    buffer = ""
    full_ai_response = ""

    tool_call_id = None
    tool_function_name = None
    tool_arguments = ""

    async for chunk in response:
        if cancelled.is_set():
            break

        delta = chunk.choices[0].delta

        if delta.tool_calls:
            tc = delta.tool_calls[0]
            if tc.id:
                tool_call_id = tc.id
            if tc.function.name:
                tool_function_name = tc.function.name
            if tc.function.arguments:
                tool_arguments += tc.function.arguments

        elif delta.content:
            text_chunk = delta.content
            full_ai_response += text_chunk
            buffer += text_chunk

            await websocket.send_json({"type": "text", "content": text_chunk})

            # Sentence boundary: split on .?! but not on common abbreviations
            if any(p in buffer for p in ['. ', '? ', '! ', '.\n', '?\n', '!\n']):
                last_idx = max(
                    buffer.rfind('. '),
                    buffer.rfind('? '),
                    buffer.rfind('! '),
                    buffer.rfind('.\n'),
                    buffer.rfind('?\n'),
                    buffer.rfind('!\n'),
                )
                if last_idx >= 0:
                    sentence = buffer[:last_idx + 1].strip()
                    buffer = buffer[last_idx + 1:]
                    if len(sentence) > 3:
                        sentence_queue.put_nowait(sentence)

    # Flush remaining buffer
    if buffer.strip() and len(buffer.strip()) > 3:
        sentence_queue.put_nowait(buffer.strip())

    if full_ai_response:
        print(f"AI: {full_ai_response}")
        conversation_history.append({"role": "assistant", "content": full_ai_response})

    # Signal TTS worker to finish
    sentence_queue.put_nowait(None)
    await tts_task

    if not cancelled.is_set():
        await websocket.send_json({"type": "audio_complete"})

    # Handle tool calls
    if tool_function_name == "close_connection":
        print("Tool Call: close_connection")
        await websocket.send_json({"type": "close"})
        return


@router.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to Voice WebSocket")

    try:
        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        conversation_history = [
            {
                "role": "system",
                "content": (
                    "You are Nephele, a college placement companion. "
                    "Keep answers brief (1-3 sentences) because they are spoken aloud. You have full memory of this conversation. "
                    "If the user says goodbye or asks to hang up, use the close_connection tool immediately. "
                    "You were built by The Cloud Pep Students, main Tech Leads Saravana and Joshua."
                )
            }
        ]

        # Cancellation event — set when a new utterance arrives to interrupt current response
        current_cancel = asyncio.Event()
        current_task: asyncio.Task | None = None

        async def on_message(self, result, **kwargs):
            nonlocal current_cancel, current_task

            sentence = result.channel.alternatives[0].transcript
            if not sentence:
                return

            if result.is_final:
                conversation_history.append({"role": "user", "content": sentence})

                # Notify frontend of user's speech
                try:
                    await websocket.send_json({"type": "user_text", "content": sentence})
                except Exception:
                    return

                # Barge-in: cancel any in-flight LLM+TTS pipeline
                if current_task and not current_task.done():
                    current_cancel.set()
                    try:
                        await asyncio.wait_for(current_task, timeout=2.0)
                    except (asyncio.TimeoutError, Exception):
                        current_task.cancel()

                # Trim history: keep system prompt + last 20 messages
                while len(conversation_history) > 21:
                    conversation_history.pop(1)

                # Launch new pipeline
                current_cancel = asyncio.Event()

                async def run_pipeline(text, cancel_evt):
                    try:
                        await generate_llm_and_tts(text, websocket, conversation_history, cancel_evt)
                    except Exception as e:
                        print(f"LLM pipeline error: {e}")

                current_task = asyncio.create_task(run_pipeline(sentence, current_cancel))

        async def on_error(self, error, **kwargs):
            print(f"Deepgram Error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            model="nova-2",
            language="en-US",
            smart_format=True,
            interim_results=False,
            encoding="linear16",
            sample_rate=16000,
            endpointing="750",
        )

        await dg_connection.start(options)

        try:
            while True:
                data = await websocket.receive_bytes()
                await dg_connection.send(data)

        except WebSocketDisconnect:
            print("Client disconnected from Voice WebSocket")
        finally:
            if current_task and not current_task.done():
                current_cancel.set()
                current_task.cancel()
            await dg_connection.finish()

    except Exception as e:
        print(f"Exception in voice route: {e}")
