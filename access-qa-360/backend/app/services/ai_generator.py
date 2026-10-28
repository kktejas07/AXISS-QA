"""
AI Test Generation Service — uses Claude Sonnet to generate Playwright Python tests
from a plain-English feature description.
"""
import asyncio
from anthropic import Anthropic
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.suite import Suite, SuiteStatus
from sqlalchemy import select

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

GENERATION_PROMPT = """You are an expert QA engineer specialising in Playwright (Python).

Given the following inputs:
- App URL: {url}
- Feature description: {description}

Generate a complete, runnable Playwright Python test file that:
1. Tests the described feature thoroughly with a realistic user journey
2. Includes the happy path AND at least 2 meaningful edge cases
3. Uses selectors in priority order: data-testid > aria-label > role > visible text
4. Includes clear assertion error messages
5. Uses async/await with pytest-playwright
6. Adds a short comment above each test explaining its purpose
7. Is fully self-contained — no external fixtures beyond `page` from pytest-playwright

Return ONLY valid Python code. No markdown fences, no explanation, no preamble.
Start with the import statements."""


async def generate_test_code(suite_id: str, base_url: str, feature_description: str) -> None:
    """Background task: call Claude Sonnet, store generated code, update suite status."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Suite).where(Suite.id == suite_id))
            suite = result.scalar_one_or_none()
            if not suite:
                return

            prompt = GENERATION_PROMPT.format(url=base_url, description=feature_description)

            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
            )

            generated_code = message.content[0].text.strip()
            suite.generated_code = generated_code
            suite.status = SuiteStatus.active
            await db.commit()

        except Exception as e:
            async with AsyncSessionLocal() as db2:
                result = await db2.execute(select(Suite).where(Suite.id == suite_id))
                suite = result.scalar_one_or_none()
                if suite:
                    suite.status = SuiteStatus.draft
                    await db2.commit()
            print(f"[AI Generator] Error for suite {suite_id}: {e}")
