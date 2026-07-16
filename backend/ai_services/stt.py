import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import io

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY) #openai client constructor

async def transcribe_audio(audio_bytes: bytes) -> str:
    print('taking in audio bytes and sending openai transcription')

    audio_file = io.BytesIO(audio_bytes) #openai needs file like object, so wrapping in iobytes object
    audio_file.name = "audio.webm" 

    try:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

        return transcript.text
    except Exception as e:
        print(f"Error during transcription: {e}")
        return ""