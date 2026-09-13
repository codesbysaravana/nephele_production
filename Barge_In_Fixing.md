# Barge-In Fixing with 3 APIs Erroring

## What Was Failing

The voice pipeline chains three APIs — Deepgram STT, OpenAI LLM, and Deepgram TTS. When the user interrupted mid-response, the system would hang for 0.5–2 seconds or silently corrupt conversation history. Each failure mapped to a different seam between the three providers.

---

## What I Fixed

### Barge-In Cancellation — `aiter_bytes()` blocking the cancel signal

**What was failing**: The cancel check ran between 4KB TTS chunks. If the network was slow and the next chunk hadn't arrived yet, the coroutine was parked inside `aiter_bytes()` waiting on I/O. The cancel signal existed but nothing was home to read it. Dead air for up to 2 seconds.

**Fix**: Implemented task racing with a 100ms poll loop — created an inner `pump_chunks()` task for the stream, and a separate poll that checks `cancelled.is_set()` every 100ms and forcefully cancels the stream task when triggered.

**File**: `backend/routes/voice_routes.py` lines 43–126

---

### TTS Worker Queue Not Draining on Cancel

**What was failing**: When cancelled mid-response, sentences already queued in `sentence_queue` weren't being cleared. The worker would attempt to process them anyway, keeping the pipeline alive longer than it should.

**Fix**: On cancel, drain the full queue before breaking:
```python
if cancelled.is_set():
    sentence_queue.task_done()
    while not sentence_queue.empty():
        try:
            sentence_queue.get_nowait()
            sentence_queue.task_done()
        except asyncio.QueueEmpty:
            break
    break
```

**File**: `backend/routes/voice_routes.py` lines 153–167

---

### Partial AI Responses Written to History on Interrupt

**What was failing**: When barge-in triggered mid-stream, `full_ai_response` was a partial sentence. It still got appended to `conversation_history`, so the LLM's next turn started from a broken mid-sentence context.

**Fix**: Guard the history append with a cancel check:
```python
if full_ai_response and not cancelled.is_set():
    async with history_lock:
        conversation_history.append(...)
```

**File**: `backend/routes/voice_routes.py` lines 274–280

---

### Conversation History Race Condition

**What was failing**: Two concurrent writes to `conversation_history` with no synchronization — `on_message()` appending the user message, and the old pipeline task appending the AI response at the same time. Interleaved writes corrupted the LLM context silently with no error.

**Fix**: `asyncio.Lock()` wrapping all history mutations:

**File**: `backend/routes/voice_routes.py`
- Line 309: lock creation
- Lines 319–320, 334–336: user message + history trim
- Lines 231–242, 249–254, 276–280: AI messages + tool calls

---

### Tool Call History Not Written in OpenAI's Required Format

**What was failing**: Tool calls weren't being appended to history with the proper structure OpenAI expects. Fine for now since `close_connection` needs no follow-up, but any tool requiring a response after execution would fail with an API error about missing `tool` role messages.

**Fix**: Proper tool call flow — write the assistant tool_call message to history, execute the tool, write the tool result message, keep text responses mutually exclusive via else branch.

**File**: `backend/routes/voice_routes.py` lines 227–283

---

## Files Changed

- `backend/routes/voice_routes.py`
  - Lines 43–126: `stream_tts_to_ws()` task racing
  - Lines 153–167: `tts_worker()` queue draining
  - Lines 227–283: tool call + history management
  - Line 309: `history_lock` creation
  - Lines 319–320, 334–336, 343: lock usage in `on_message()`
