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

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(title="Nephele Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
async def welcome():
    return {"status": "Nephele Backend Welcome"}

@app.get("/health")
async def health_check():
    return {"status": "Nephele is awake and listening!"}

@app.post("/api/attendance")
async def take_attendance(request: Request):
    data = await request.json()
    logger.info(f"✅ Attendance Logged: {data}")
    return {"status": "success", "message": "Attendance saved!"}

# Speech-To-Text (NOVA 2 MODEL)
DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&endpointing=300"
API_KEY = os.getenv("DEEPGRAM_API_KEY")

@app.websocket("/ws/audio")
async def audio_websocket_endpoint(websocket: WebSocket):
    await websocket.accept() # browser connection
    logger.info("Started the websocket endpoint")
    
    extra_headers = {
        "Authorization": f"Token {API_KEY}"
    }

    try: # websocket connection to deepgram since ws is allowed
        async with websockets.connect(DEEPGRAM_URL, additional_headers=extra_headers) as dg_ws:
            logger.info("Connected to Deepgram directly!")

            async def browser_to_deepgram():
                try:
                    while True:
                        message = await websocket.receive()
                        
                        if message["type"] == "websocket.disconnect":
                            logger.info("Browser disconnected gracefully.")
                            break
                            
                        if "bytes" in message and message["bytes"]:
                            await dg_ws.send(message["bytes"])
                            
                except Exception as e:
                    logger.error(f"Browser to Deepgram stopped: {e}")

            async def deepgram_to_brain():
                try:
                    while True:
                        msg = await dg_ws.recv()
                        response = json.loads(msg)
                        
                        #(Endpointing/VAD)
                        if response.get("type") == "Results":
                            is_final = response.get("is_final", False)
                            speech_final = response.get("speech_final", False)
                            
                            if is_final or speech_final:
                                alternatives = response.get("channel", {}).get("alternatives", [])
                                if alternatives:
                                    sentence = alternatives[0].get("transcript", "")
                                    if sentence and speech_final:
                                        logger.info(f"🎤 VAD Detected Silence! Transcript: {sentence}")
                                        asyncio.create_task(run_brain(sentence, websocket))
                except Exception as e:
                    logger.error(f"Deepgram to Brain stopped: {e}")

            await asyncio.gather( #running at the same time
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
        async for chunk in process_voice_pipeline(text):
            if isinstance(chunk, str):
                await websocket.send_text(chunk)
                logger.info(f"📡 Sent JSON command to frontend: {chunk}")
            else:
                await websocket.send_bytes(chunk)
                logger.info("🔊 Sent a sentence of TTS audio back to frontend!")
    except Exception as e:
        logger.error(f"Error in brain: {e}")

if __name__ == "__main__":
    logger.info("starting up the uvicorn server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)