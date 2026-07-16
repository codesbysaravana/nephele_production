import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def generate_speech(text: str) -> bytes:
    print(f"Generating audio for text: '{text}'")
    
    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice="alloy", 
            input=text,
            response_format="opus"
        )
        
        return response.read()
    except Exception as e:
        print(f"Error during TTS: {e}")
        return b""
