from app.worker.celery_app import celery_app
from app.services.runner import run_playwright_tests
from app.services.triage import triage_failure
from app.core.database import AsyncSessionLocal
from app.models.run import Run, RunStatus
from sqlalchemy import select
from datetime import datetime, timezone
import asyncio


@celery_app.task(bind=True, max_retries=1)
def execute_test_run(self, run_id: str, test_code: str):
    """Celery task: run Playwright tests, update Run record, triage failures."""
    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if not run:
                return

            run.status = RunStatus.running
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

        test_result = run_playwright_tests(test_code)

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if not run:
                return

            run.status = RunStatus.passed if test_result["passed"] else RunStatus.failed
            run.duration_ms = test_result["duration_ms"]
            run.stdout_log = test_result["stdout"]
            run.error_message = test_result["error"] or None
            run.tests_total = test_result["tests_total"]
            run.tests_passed = test_result["tests_passed"]
            run.tests_failed = test_result["tests_failed"]
            run.finished_at = datetime.now(timezone.utc)

            if not test_result["passed"] and test_result["error"]:
                run.triage_summary = triage_failure(test_result["stdout"], test_result["error"])

            await db.commit()

    asyncio.run(_run())
