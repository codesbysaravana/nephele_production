import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio

from ai_services.tts import generate_speech

load_dotenv() 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# This is the "Persona" of your robot
SYSTEM_PROMPT = """
You are Nephele, a fast, friendly AI companion created by the PeP Cloud students.
Respond conversationally in no more than 3 short sentences. Give the direct answer first, avoid filler, and only expand if the user explicitly asks. Speak naturally as if talking to a friend.
If someone asks who created you, say you were built by the PeP Cloud students. Never bring it up unless it's relevant or you're asked.
"""

async def process_voice_pipeline(user_text: str):
    """
    The Brain & Mouth!
    2. LLM (Streaming) -> 3. TTS (Streaming chunks)
    Yields audio bytes as soon as a sentence is ready.
    """
    if not user_text:
        return
    
    print(f"User said: {user_text}")

    # 2. Call the LLM (The Brain) and stream the response!
    stream = await client.chat.completions.create(
        model="gpt-4o", # Or gpt-3.5-turbo for cheaper/faster
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        stream=True
    )

    sentence_buffer = ""
    
    # Iterate through the words as the AI thinks of them
    async for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            word = chunk.choices[0].delta.content
            sentence_buffer += word
            
            # If we hit a punctuation mark, we have a complete thought!
            if any(char in word for char in ['.', '!', '?']):
                clean_sentence = sentence_buffer.strip()
                if clean_sentence:
                    print(f"🤖 Brain thought of a sentence: {clean_sentence}")
                    
                    # 3. IMMEDIATELY send this single sentence to TTS
                    audio_bytes = await generate_speech(clean_sentence)
                    
                    # 4. Yield the audio chunk back to main.py to send to the browser
                    if audio_bytes:
                        yield audio_bytes
                    
                # Reset the buffer for the next sentence
                sentence_buffer = ""
                
    # Catch any leftover words that didn't end in punctuation
    if sentence_buffer.strip():
        print(f"🤖 Brain thought of final sentence: {sentence_buffer.strip()}")
        audio_bytes = await generate_speech(sentence_buffer.strip())
        if audio_bytes:
            yield audio_bytes
