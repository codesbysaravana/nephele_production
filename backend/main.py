import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
import websockets
import json

from ai_services.openai import process_voice_pipeline

load_dotenv().lu7uj
logger = logging.getLogger(__name__)

app = FastAPI(title="Nephele Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&endpointing=300"
API_KEY = os.getenv("DEEPGRAM_API_KEY")

@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Started the websocket endpoint")
    
    extra_headers = {
        "Authorization": f"Token {API_KEY}"
    }

    try:
        # Open connection to Deepgram
        async with websockets.connect(DEEPGRAM_URL, additional_headers=extra_headers) as dg_ws:
            logger.info("Connected to Deepgram directly!")

            # Task 1: Receive from Browser -> Send to Deepgram
            async def browser_to_deepgram():
                try:
                    while True:
                        message = await websocket.receive()
                        
                        # If the user clicked Stop, break the loop cleanly!
                        if message["type"] == "websocket.disconnect":
                            logger.info("Browser disconnected gracefully.")
                            break
                            
                        # If we got audio bytes, send them to Deepgram
                        if "bytes" in message and message["bytes"]:
                            await dg_ws.send(message["bytes"])
                            
                except Exception as e:
                    logger.error(f"Browser to Deepgram stopped: {e}")

            # Task 2: Receive from Deepgram -> Trigger AI Brain
            async def deepgram_to_brain():
                try:
                    while True:
                        msg = await dg_ws.recv()
                        response = json.loads(msg)
                        
                        # We only care about transcripts that are "speech_final" (Endpointing/VAD)
                        if response.get("type") == "Results":
                            is_final = response.get("is_final", False)
                            speech_final = response.get("speech_final", False)
                            
                            if is_final or speech_final:
                                alternatives = response.get("channel", {}).get("alternatives", [])
                                if alternatives:
                                    sentence = alternatives[0].get("transcript", "")
                                    if sentence and speech_final:
                                        logger.info(f"🎤 VAD Detected Silence! Transcript: {sentence}")
                                        # Fire off the LLM Brain in the background
                                        asyncio.create_task(run_brain(sentence, websocket))
                except Exception as e:
                    logger.error(f"Deepgram to Brain stopped: {e}")

            # Run both tasks concurrently
            await asyncio.gather(
                browser_to_deepgram(),
                deepgram_to_brain()
            )

    except WebSocketDisconnect:
        logger.info("Frontend completely disconnected.")
    except Exception as e:
        logger.error(f"Error in websocket endpoint: {e}")

async def run_brain(text: str, websocket: WebSocket):
    """Takes the VAD text, runs the LLM -> TTS stream, and sends audio back to the browser."""
    try:
        async for audio_chunk in process_voice_pipeline(text):
            await websocket.send_bytes(audio_chunk)
            logger.info("🔊 Sent a sentence of TTS audio back to frontend!")
    except Exception as e:
        logger.error(f"Error in brain: {e}")

if __name__ == "__main__":
    logger.info("starting up the uvicorn server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)