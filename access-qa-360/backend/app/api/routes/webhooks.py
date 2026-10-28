from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.suite import Suite
from app.models.run import Run
from app.worker.tasks import execute_test_run
import json

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github/{project_id}")
async def github_webhook(project_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Trigger runs for all active suites in a project on GitHub PR events."""
    payload = await request.body()
    event = request.headers.get("X-GitHub-Event", "")
    if event not in ("pull_request", "push"):
        return {"status": "ignored", "reason": f"event {event} not handled"}

    data = json.loads(payload)
    branch = data.get("pull_request", {}).get("head", {}).get("ref") or data.get("ref", "").replace("refs/heads/", "")
    commit_sha = data.get("pull_request", {}).get("head", {}).get("sha") or data.get("after", "")

    result = await db.execute(
        select(Suite).where(Suite.project_id == project_id, Suite.status == "active", Suite.generated_code.isnot(None))
    )
    suites = result.scalars().all()

    run_ids = []
    for suite in suites:
        run = Run(suite_id=suite.id, triggered_by="github_pr", branch=branch, commit_sha=commit_sha)
        db.add(run)
        await db.flush()
        execute_test_run.delay(run.id, suite.generated_code)
        run_ids.append(run.id)

    return {"status": "queued", "run_ids": run_ids, "suites_triggered": len(run_ids)}
