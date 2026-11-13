"""Starting and stopping scans that run inside this process."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_job import AuditJob, AuditStatus

# Running scans by id. Holding the task also stops the event loop dropping it mid-run.
_tasks: dict[str, asyncio.Task] = {}


def launch(job_id: str) -> None:
    from app.services import audit_orchestrator

    task = asyncio.create_task(audit_orchestrator.run_audit(job_id))
    _tasks[job_id] = task
    task.add_done_callback(lambda _: _tasks.pop(job_id, None))


def is_running_here(job_id: str) -> bool:
    return job_id in _tasks


class NotActive(Exception):
    pass


async def stop(db: AsyncSession, job: AuditJob, reason: str) -> AuditJob:
    """
    Stop a queued or running scan and mark it failed with `reason`.

    Also clears scans left "running" by a restart: their work is gone, so they
    are simply marked as stopped.
    """
    status = job.status.value if hasattr(job.status, "value") else str(job.status)
    if status not in ("queued", "running") or not job.started_at:
        raise NotActive()
    task = _tasks.get(job.id)
    if task and not task.done():
        task.cancel()
        # Let the scan finish its clean-up (deleting uploaded code) before the final state is written.
        await asyncio.gather(task, return_exceptions=True)
        await db.refresh(job)
    for n in range(1, 6):
        if getattr(job, f"tier{n}_status") in ("running", "pending"):
            was_running = getattr(job, f"tier{n}_status") == "running"
            setattr(job, f"tier{n}_status", "failed" if was_running else "skipped")
            setattr(job, f"tier{n}_result", {"error": reason} if was_running else {"skipped": reason})
    job.status = AuditStatus.failed
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return job
