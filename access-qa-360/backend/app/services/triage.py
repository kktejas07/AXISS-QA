"""
Failure Triage Service — uses Claude Haiku to summarise test failures cheaply.
"""
from app.core.ai import sync_ai_client
from app.core.config import settings

client = sync_ai_client("Run triage")

TRIAGE_PROMPT = """You are a QA engineer triaging an automated test failure.

Test stdout / stderr:
{stdout}

Error message:
{error}

In 3 bullet points (each under 20 words), identify:
- The most likely root cause
- Whether this is a flake or a real bug
- The recommended next action for a developer

Be direct and technical. No preamble."""


def triage_failure(stdout: str, error: str) -> str:
    """Synchronous call — runs inside a Celery worker."""
    try:
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": TRIAGE_PROMPT.format(stdout=stdout[:3000], error=error[:500])}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        return f"Triage unavailable: {e}"
