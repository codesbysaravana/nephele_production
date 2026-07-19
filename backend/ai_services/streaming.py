"""
Shared streaming utilities for all voice brain modules.
Handles: LLM stream parsing, sentence-level TTS dispatch, tool-result synthesis.
"""

import json
from openai import AsyncOpenAI
from ai_services.tts import generate_speech


async def stream_llm_response(client: AsyncOpenAI, messages: list, tools: list | None = None):
    """
    Stream an LLM call. Yields audio bytes for each sentence.
    Returns (full_text, tool_name, tool_args) after the stream ends.

    If the LLM calls a tool instead of speaking, full_text will be empty
    and tool_name/tool_args will be populated.
    """
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        stream=True,
    )

    sentence_buffer = ""
    full_text = ""
    tool_name = ""
    tool_args = ""
    is_tool = False

    async for chunk in stream:
        delta = chunk.choices[0].delta

        if delta.tool_calls:
            is_tool = True
            tc = delta.tool_calls[0]
            if tc.function.name:
                tool_name = tc.function.name
            if tc.function.arguments:
                tool_args += tc.function.arguments
            continue

        if delta.content and not is_tool:
            sentence_buffer += delta.content
            full_text += delta.content

            if any(c in delta.content for c in ".!?"):
                clean = sentence_buffer.strip()
                if clean:
                    audio = await generate_speech(clean)
                    if audio:
                        yield audio
                sentence_buffer = ""

    # Flush remaining text
    if sentence_buffer.strip() and not is_tool:
        audio = await generate_speech(sentence_buffer.strip())
        if audio:
            yield audio

    # Attach metadata to the generator's return (accessed via StopIteration.value won't work
    # for async generators, so we use a final sentinel yield)
    yield ("__result__", full_text, tool_name, tool_args)


async def synthesize_tool_result(client: AsyncOpenAI, system_prompt: str, history: list):
    """
    After a tool executes, call the LLM again to synthesize a spoken answer.
    Yields audio bytes for each sentence.
    Returns the full synthesized text.
    """
    messages = [{"role": "system", "content": system_prompt}] + history

    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        stream=True,
    )

    sentence_buffer = ""
    full_text = ""

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            sentence_buffer += delta.content
            full_text += delta.content

            if any(c in delta.content for c in ".!?"):
                clean = sentence_buffer.strip()
                if clean:
                    audio = await generate_speech(clean)
                    if audio:
                        yield audio
                sentence_buffer = ""

    if sentence_buffer.strip():
        audio = await generate_speech(sentence_buffer.strip())
        if audio:
            yield audio

    yield ("__result__", full_text)
