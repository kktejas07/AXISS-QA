"""Earlier scans of the same website, repository or app."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_job import AuditJob, AuditStatus

DONE = (AuditStatus.completed, AuditStatus.partial)


def _same_target(job: AuditJob):
    q = select(AuditJob).where(AuditJob.organization_id == job.organization_id, AuditJob.source_type == job.source_type, AuditJob.id != job.id)
    if job.source_type == "web":
        return q.where(AuditJob.target_url.in_({job.target_url, (job.target_url or "").rstrip("/"), (job.target_url or "").rstrip("/") + "/"}))
    if job.source_type == "repo":
        return q.where(AuditJob.repo_url == job.repo_url)
    if job.app_name:
        return q.where(AuditJob.app_name == job.app_name)
    return q.where(AuditJob.app_name.is_(None), AuditJob.source_filename == job.source_filename)


async def previous(db: AsyncSession, job: AuditJob) -> AuditJob | None:
    """
    The finished scan to compare this one with: the one before it. A pull-request
    scan is compared with the latest scan of the repository's main line instead.
    """
    q = _same_target(job).where(AuditJob.status.in_(DONE), AuditJob.created_at <= job.created_at)
    if (job.trigger or {}).get("kind") == "pull_request":
        q = q.where(AuditJob.repo_ref.is_(None))
    elif job.source_type == "repo":
        q = q.where(AuditJob.repo_ref.is_(None) if job.repo_ref is None else AuditJob.repo_ref == job.repo_ref)
    return (await db.execute(q.order_by(AuditJob.created_at.desc()).limit(1))).scalars().first()


async def series(db: AsyncSession, job: AuditJob, limit: int = 12) -> list[AuditJob]:
    """This scan and the finished ones of the same target, oldest first."""
    q = _same_target(job).where(AuditJob.status.in_(DONE))
    if job.source_type == "repo":
        q = q.where(or_(AuditJob.repo_ref.is_(None), AuditJob.repo_ref == job.repo_ref))
    rows = list((await db.execute(q.order_by(AuditJob.created_at.desc()).limit(limit - 1))).scalars().all())
    return sorted(rows + [job], key=lambda j: j.created_at)
