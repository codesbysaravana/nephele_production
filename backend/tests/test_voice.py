import asyncio
import os
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("DEEPGRAM_API_KEY", None)
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from main import app
from routes import voice_routes as voice


class AppTests(unittest.TestCase):
    def test_health_without_keys(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").json(), {"status": "ok", "voice_configured": False})
            self.assertEqual(client.get("/").status_code, 200)

    def test_missing_keys_reported_to_client(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:5173"}) as ws:
                self.assertEqual(ws.receive_json()["type"], "error")
                with self.assertRaises(WebSocketDisconnect) as closed:
                    ws.receive_json()
                self.assertEqual(closed.exception.code, 1011)

    def test_unknown_origin_rejected_before_provider_use(self):
        with TestClient(app) as client:
            with self.assertRaises(WebSocketDisconnect) as closed:
                with client.websocket_connect("/ws/voice", headers={"origin": "https://untrusted.example"}):
                    pass
            self.assertEqual(closed.exception.code, 1008)


class Stream:
    def __init__(self, deltas):
        self.deltas = deltas
        self.closed = False
    async def __aiter__(self):
        for delta in self.deltas:
            yield NS(choices=[NS(delta=NS(content=delta, tool_calls=None))])
    async def close(self):
        self.closed = True


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_text_speech_history_and_completion(self):
        response = Stream(["Hello. ", "You can practice with me."])
        llm = NS(chat=NS(completions=NS(create=AsyncMock(return_value=response))))
        ws = NS(send_json=AsyncMock(), send_bytes=AsyncMock())
        history = [{"role": "system", "content": "test"}, {"role": "user", "content": "Hi"}]
        with patch.object(voice, "stream_tts_to_ws", new_callable=AsyncMock) as tts:
            await voice.generate_llm_and_tts("Hi", ws, history, asyncio.Event(), asyncio.Lock(), llm, None, "test")
        self.assertEqual(tts.await_count, 2)
        self.assertEqual(history[-1], {"role": "assistant", "content": "Hello. You can practice with me."})
        self.assertEqual(ws.send_json.call_args.args[0], {"type": "audio_complete"})
        self.assertTrue(response.closed)

    async def test_barge_in_cancels_tts_while_waiting_for_network(self):
        started = asyncio.Event()
        finished = asyncio.Event()
        async def slow_tts(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()
        response = Stream(["A sentence. "])
        llm = NS(chat=NS(completions=NS(create=AsyncMock(return_value=response))))
        ws = NS(send_json=AsyncMock())
        with patch.object(voice, "stream_tts_to_ws", side_effect=slow_tts):
            task = asyncio.create_task(voice.generate_llm_and_tts("Hi", ws, [], asyncio.Event(), asyncio.Lock(), llm, None, "test"))
            await asyncio.wait_for(started.wait(), 1)
            await asyncio.wait_for(voice.cancel_task(task), 1)
        self.assertTrue(finished.is_set())
        self.assertTrue(response.closed)
        self.assertTrue(task.cancelled())

    async def test_tts_error_does_not_deadlock_a_full_queue(self):
        response = Stream(["Test. "] * 30)
        llm = NS(chat=NS(completions=NS(create=AsyncMock(return_value=response))))
        ws = NS(send_json=AsyncMock())
        with patch.object(voice, "stream_tts_to_ws", new_callable=AsyncMock, side_effect=RuntimeError("provider unavailable")):
            with self.assertRaises(RuntimeError):
                await asyncio.wait_for(voice.generate_llm_and_tts("Hi", ws, [], asyncio.Event(), asyncio.Lock(), llm, None, "test"), 1)
        self.assertTrue(response.closed)

    async def test_pre_cancelled_turn_does_not_call_provider(self):
        cancelled = asyncio.Event()
        cancelled.set()
        llm = NS(chat=NS(completions=NS(create=AsyncMock())))
        await voice.generate_llm_and_tts("Hi", None, [], cancelled, asyncio.Lock(), llm, None, "test")
        llm.chat.completions.create.assert_not_called()

    def test_bounded_history_preserves_system_and_starts_with_user(self):
        history = [{"role": "system", "content": "test"}] + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(50)
        ]
        voice.trim_history(history)
        self.assertLessEqual(len(history), 21)
        self.assertEqual(history[0]["role"], "system")
        self.assertEqual(history[1]["role"], "user")

class MockConnectionTests(unittest.TestCase):
    def test_ready_utterance_and_disconnect_cleanup(self):
        events = {}
        finished = []
        pipelines = []

        class DG:
            def on(self, event, callback):
                events[event] = callback
            async def start(self, options):
                return True
            async def send(self, data):
                for sentence, final in [("First segment", False), ("second segment", True)]:
                    result = NS(channel=NS(alternatives=[NS(transcript=sentence)]), is_final=True, speech_final=final)
                    await events[voice.LiveTranscriptionEvents.Transcript](self, result=result)
            async def finish(self):
                finished.append(True)

        dg = DG()
        async def pipeline(text, *args):
            pipelines.append(text)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-a-real-key", "DEEPGRAM_API_KEY": "test-not-a-real-key"}), \
             patch.object(voice, "DeepgramClient", return_value=NS(listen=NS(asyncwebsocket=NS(v=lambda _: dg)))), \
             patch.object(voice, "generate_llm_and_tts", side_effect=pipeline):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/voice", headers={"origin": "http://localhost:5173"}) as ws:
                    self.assertEqual(ws.receive_json(), {"type": "ready"})
                    ws.send_bytes(b"\x00\x00")
                    self.assertEqual(ws.receive_json(), {"type": "user_text", "content": "First segment second segment"})
        self.assertEqual(finished, [True])
        self.assertEqual(pipelines, ["First segment second segment"])
