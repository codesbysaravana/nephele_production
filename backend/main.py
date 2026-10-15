"""Run with `uvicorn main:app --host 0.0.0.0 --port $PORT` from backend/."""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from routes.voice_routes import router as voice_router  # noqa: E402

app = FastAPI(title="Nephele Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(voice_router)


@app.get("/")
async def welcome():
    return {"status": "Nephele Backend Welcome"}


@app.get("/health")
async def health():
    # Do not expose keys or make billable provider calls from a health probe.
    return {"status": "ok", "voice_configured": bool(
        os.getenv("OPENAI_API_KEY") and os.getenv("DEEPGRAM_API_KEY")
    )}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
