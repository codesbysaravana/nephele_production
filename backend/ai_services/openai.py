import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio

from ai_services.tts import generate_speech

load_dotenv() 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# IN-MEMORY STATE (Resets when the server restarts)
conversation_history = [] # Short-Term Memory: Rolling window of the last 10 messages
saved_facts = [] # Long-Term Memory: Facts saved by the LLM

SYSTEM_PROMPT = """
You are Nephele, a fast, friendly AI companion created by the PeP Cloud students.
Respond conversationally in no more than 3 short sentences. Give the direct answer first, avoid filler, and only expand if the user explicitly asks. Speak naturally as if talking to a friend.
If someone asks who created you, say you were built by the PeP Cloud students. Never bring it up unless it's relevant or you're asked.
"""

# Define the Tool for OpenAI
tools = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save an important fact about the user or the conversation to long-term memory so you don't forget it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The fact to remember. E.g., 'The user's dog is named Max.'"
                    }
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_attendance_mode",
            "description": "Trigger this tool if the user asks you to take attendance or scan a QR code.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

async def process_voice_pipeline(user_text: str):
    global conversation_history, saved_facts
    
    if not user_text:
        return
    
    print(f"\n🗣️ User said: {user_text}")

    # 1. Update Short-Term Memory
    conversation_history.append({"role": "user", "content": user_text})
    if len(conversation_history) > 10:
        conversation_history.pop(0)

    # 2. Inject Long-Term Memory dynamically into the system prompt
    dynamic_system_prompt = SYSTEM_PROMPT
    if saved_facts:
        dynamic_system_prompt += "\n\nHere are some facts you have saved about the user:\n"
        for fact in saved_facts:
            dynamic_system_prompt += f"- {fact}\n"

    # Build the messages array with context
    messages = [{"role": "system", "content": dynamic_system_prompt}] + conversation_history

    # 3. Call LLM with Tool capabilities (Streaming)
    stream = await client.chat.completions.create(
        model="gpt-4o", 
        messages=messages,
        tools=tools,
        stream=True
    )

    sentence_buffer = ""
    full_assistant_reply = ""
    
    # Tool extraction variables
    is_tool_call = False
    tool_name = ""
    tool_args_buffer = ""
    
    async for chunk in stream:
        delta = chunk.choices[0].delta
        
        # Check if the LLM decided to use a tool!
        if delta.tool_calls:
            is_tool_call = True
            tool_call = delta.tool_calls[0]
            if tool_call.function.name:
                tool_name = tool_call.function.name
            if tool_call.function.arguments:
                tool_args_buffer += tool_call.function.arguments
            continue

        # Normal text streaming
        if delta.content is not None and not is_tool_call:
            word = delta.content
            sentence_buffer += word
            full_assistant_reply += word
            
            if any(char in word for char in ['.', '!', '?']):
                clean_sentence = sentence_buffer.strip()
                if clean_sentence:
                    print(f"🤖 Brain thought of a sentence: {clean_sentence}")
                    audio_bytes = await generate_speech(clean_sentence)
                    if audio_bytes:
                        yield audio_bytes
                sentence_buffer = ""
                
    # 4. Handle Tool Execution after the stream finishes
    if is_tool_call:
        if tool_name == "save_memory":
            try:
                args = json.loads(tool_args_buffer)
                fact = args.get("fact", "")
                if fact:
                    print(f"💾 SAVING LONG-TERM MEMORY: {fact}")
                    saved_facts.append(fact)
                    
                    ack_sentence = "Got it, I'll commit that to memory."
                    print(f"🤖 Brain thought of a sentence: {ack_sentence}")
                    full_assistant_reply = ack_sentence
                    audio_bytes = await generate_speech(ack_sentence)
                    if audio_bytes:
                        yield audio_bytes
            except Exception as e:
                print(f"Error parsing tool args: {e}")
                
        elif tool_name == "trigger_attendance_mode":
            print("📷 Triggering Attendance Mode UI Route!")
            # Yield a JSON command string instead of raw audio bytes
            command_json = json.dumps({"command": "route", "path": "#/attendance"})
            yield command_json

    # Catch leftover words
    if sentence_buffer.strip() and not is_tool_call:
        print(f"🤖 Brain thought of final sentence: {sentence_buffer.strip()}")
        audio_bytes = await generate_speech(sentence_buffer.strip())
        if audio_bytes:
            yield audio_bytes

    # 5. Save the assistant's reply to Short-Term Memory
    if full_assistant_reply:
        conversation_history.append({"role": "assistant", "content": full_assistant_reply})
        if len(conversation_history) > 10:
            conversation_history.pop(0)
