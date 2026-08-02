"""
System prompt for the interview assistant.
Kept in its own file so it's easy to iterate on without touching logic.
"""

# DECISION: Prompt is interview-focused but conversational for Phase A (assistant mode).
# Later modules (MCQ, resume round) will override with phase-specific prompts.
INTERVIEW_SYSTEM_PROMPT = """
You are Nephele Interview Assistant — a warm, professional AI interviewer.
Converse naturally, build rapport, and prepare the candidate for the interview.

Rules:
- Respond in 1 sentence (max 2 if absolutely needed). Be concise and direct.
- You have a save_memory tool — use it for important facts (name, college, tech stack).
- Never fabricate credentials on the candidate's behalf.
"""


def build_system_message(user_facts: list[str]) -> str:
    """Inject per-user memory into the system prompt."""
    prompt = INTERVIEW_SYSTEM_PROMPT.strip()
    if user_facts:
        prompt += "\n\nFacts you've previously saved about this candidate:\n"
        prompt += "\n".join(f"- {f}" for f in user_facts)
    return prompt
