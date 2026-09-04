import os
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
import websockets
from routes.voice_routes import router as voice_router

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

DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&endpointing=300"
API_KEY = os.getenv("DEEPGRAM_API_KEY")

app.include_router(voice_router)

@app.get("/")
async def welcome():
    return {"status": "Nephele Backend Welcome"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
