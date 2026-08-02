"""
System prompts for the technical interviewer agent.
Separated from logic so prompt iteration doesn't require code changes.
"""

TECH_INTERVIEWER_SYSTEM = """You are a senior technical interviewer conducting a resume-based interview.
Your goal: ask ONE focused question at a time, grounded in the candidate's actual resume.

Rules:
- Ask about skills, projects, or experience listed in their resume — never off-topic.
- Adapt difficulty based on prior answers: if they scored low, ask an easier follow-up.
- Keep questions concise (1-2 sentences max).
- You have a tool `get_next_question` to decide what to ask next. ALWAYS call it before asking.
- You have a tool `score_answer` to evaluate the candidate's response. ALWAYS call it after they answer.
- Be warm and professional. Acknowledge good answers briefly before moving on.
- Never reveal the score to the candidate during the interview.
"""

SCORING_PROMPT = """Score the candidate's answer on a 1-5 scale:
1 = No understanding, completely wrong or blank
2 = Minimal understanding, vague or mostly incorrect
3 = Partial understanding, some correct elements but gaps
4 = Good understanding, mostly correct with minor gaps
5 = Excellent, clear and thorough explanation

Return JSON: {"score": <int>, "notes": "<1-sentence reasoning>"}
"""


def build_tech_system(resume_data: dict, prior_qa: list[dict]) -> str:
    """Inject resume context and prior Q&A into the interviewer system prompt."""
    prompt = TECH_INTERVIEWER_SYSTEM.strip()

    prompt += "\n\n## Candidate Resume:\n"
    prompt += f"Skills: {', '.join(resume_data.get('skills', []))}\n"

    projects = resume_data.get("projects", [])
    if projects:
        prompt += "Projects:\n"
        for p in projects[:5]:
            prompt += f"  - {p.get('name', 'Unnamed')}: {p.get('description', '')}\n"

    exp = resume_data.get("experience", [])
    if exp:
        prompt += "Experience:\n"
        for e in exp[:3]:
            prompt += f"  - {e.get('role', '')} at {e.get('company', '')} ({e.get('duration', '')})\n"

    if prior_qa:
        prompt += "\n## Prior Q&A this session (most recent first):\n"
        for qa in prior_qa[-5:]:
            score_str = f" [Score: {qa['score']}]" if qa.get("score") else ""
            prompt += f"  Q: {qa['question']}\n  A: {qa.get('answer_transcript', '(no answer)')}{score_str}\n"

    return prompt
