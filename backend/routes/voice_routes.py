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
    """
    Stream a single sentence's TTS audio to the client.
    Stops early if cancelled by racing the stream task against cancel checks.
    """
    stream_task = None

    try:
        async with _tts_http_client.stream(
            "POST",
            TTS_URL,
            headers=TTS_HEADERS,
            json={"text": sentence}
        ) as r:
            if r.status_code != 200:
                body = await r.aread()
                print(f"TTS Error: {r.status_code} {body.decode()}")
                return

            # Define the streaming pump as a separate coroutine
            async def pump_chunks():
                """Inner coroutine that does the actual streaming."""
                try:
                    async for chunk in r.aiter_bytes(4096):
                        # Check cancel even during iteration
                        if cancelled.is_set():
                            return
                        # Send with timeout to detect dead clients
                        try:
                            await asyncio.wait_for(
                                websocket.send_bytes(chunk),
                                timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            print("WebSocket send timeout — client too slow or disconnected")
                            return
                except asyncio.CancelledError:
                    # Task was cancelled externally (expected during barge-in)
                    return

            # Launch the pump as a task
            stream_task = asyncio.create_task(pump_chunks())

            # Poll loop: check cancel signal every 100ms while stream runs
            while not stream_task.done():
                try:
                    # Shield prevents our wait_for from cancelling stream_task
                    await asyncio.wait_for(
                        asyncio.shield(stream_task),
                        timeout=0.1  # 100ms polling interval
                    )
                    # If we get here, stream_task completed successfully
                    break
                except asyncio.TimeoutError:
                    # 100ms elapsed, check cancel signal
                    if cancelled.is_set():
                        # User barged in — forcefully cancel the stream
                        stream_task.cancel()
                        try:
                            await stream_task  # Wait for cancellation to complete
                        except asyncio.CancelledError:
                            pass
                        return
                    # Not cancelled yet, continue polling
                    continue

            # Stream completed naturally
            await stream_task  # Retrieve any exception that occurred

    except asyncio.CancelledError:
        # Parent task was cancelled (e.g., websocket disconnect)
        if stream_task and not stream_task.done():
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
        raise  # Propagate cancellation up

    except Exception as e:
        print(f"TTS Network Error: {e}")
        if stream_task and not stream_task.done():
            stream_task.cancel()


async def generate_llm_and_tts(
    transcript: str,
    websocket: WebSocket,
    conversation_history: list,
    cancelled: asyncio.Event,
    history_lock: asyncio.Lock,
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
                sentence_queue.task_done()
                break
            if cancelled.is_set():
                sentence_queue.task_done()
                # Drain remaining sentences to prevent queue blocking
                while not sentence_queue.empty():
                    try:
                        sentence_queue.get_nowait()
                        sentence_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
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

    # Signal TTS worker to finish
    sentence_queue.put_nowait(None)
    await tts_task

    # ========== CRITICAL SECTION: Update conversation history ==========

    # Case 1: Tool was called
    if tool_function_name:
        async with history_lock:
            conversation_history.append({
                "role": "assistant",
                "tool_calls": [{
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tool_function_name,
                        "arguments": tool_arguments
                    }
                }]
            })

        # Execute the tool
        if tool_function_name == "close_connection":
            print("Tool Call: close_connection")

            # Append tool result to history (for completeness)
            async with history_lock:
                conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": "Connection closed successfully"
                })

            # Notify client and close
            if not cancelled.is_set():
                await websocket.send_json({"type": "audio_complete"})
            await websocket.send_json({"type": "close"})
            return

        # Future tools would be handled here
        # elif tool_function_name == "search_companies":
        #     result = await search_companies(tool_arguments)
        #     async with history_lock:
        #         conversation_history.append({
        #             "role": "tool",
        #             "tool_call_id": tool_call_id,
        #             "content": json.dumps(result)
        #         })

    # Case 2: Normal text response
    else:
        if full_ai_response and not cancelled.is_set():
            print(f"AI: {full_ai_response}")
            async with history_lock:
                conversation_history.append({
                    "role": "assistant",
                    "content": full_ai_response
                })

    # Signal audio completion (if not already sent)
    if not cancelled.is_set():
        await websocket.send_json({"type": "audio_complete"})


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

        current_cancel = asyncio.Event()
        current_task: asyncio.Task | None = None
        history_lock = asyncio.Lock()

        async def on_message(result, **kwargs):
            nonlocal current_cancel, current_task, history_lock

            sentence = result.channel.alternatives[0].transcript
            if not sentence:
                return

            if result.is_final:
                async with history_lock:
                    conversation_history.append({"role": "user", "content": sentence})

                try:
                    await websocket.send_json({"type": "user_text", "content": sentence})
                except Exception:
                    return

                if current_task and not current_task.done():
                    current_cancel.set()
                    try:
                        await asyncio.wait_for(current_task, timeout=2.0)
                    except (asyncio.TimeoutError, Exception):
                        current_task.cancel()

                async with history_lock:
                    while len(conversation_history) > 21:
                        conversation_history.pop(1)

                # Launch new pipeline
                current_cancel = asyncio.Event()

                async def run_pipeline(text, cancel_evt):
                    try:
                        await generate_llm_and_tts(text, websocket, conversation_history, cancel_evt, history_lock)
                    except Exception as e:
                        print(f"LLM pipeline error: {e}")

                current_task = asyncio.create_task(run_pipeline(sentence, current_cancel))

        async def on_error(error, **kwargs):
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
