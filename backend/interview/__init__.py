# DECISION: Expose only the FastAPI router so main.py has a single import.
from interview.router import router  # noqa: F401
