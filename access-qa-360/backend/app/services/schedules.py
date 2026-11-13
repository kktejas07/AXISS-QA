"""Starting scheduled scans when they fall due."""
from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.audit_job import AuditJob
from app.models.automation import ScanSchedule
from app.models.organization import Organization
from app.services import scan_control
from app.services.orgs import scans_this_month

log = logging.getLogger(__name__)


def advance(when: datetime, frequency: str) -> datetime:
    if frequency == "daily":
        return when + timedelta(days=1)
    if frequency == "weekly":
        return when + timedelta(weeks=1)
    year, month = (when.year + 1, 1) if when.month == 12 else (when.year, when.month + 1)
    return when.replace(year=year, month=month, day=min(when.day, calendar.monthrange(year, month)[1]))


def next_after(when: datetime, frequency: str, now: datetime) -> datetime:
    """The first slot after `now`; a server that was off for a week runs each schedule once, not seven times."""
    if when.tzinfo is None:      # some databases hand times back without their zone; they are stored in UTC
        when = when.replace(tzinfo=timezone.utc)
    while when <= now:
        when = advance(when, frequency)
    return when


async def blocked(db: AsyncSession, org: Organization | None) -> str | None:
    """Why this organisation cannot start a scan right now, or None if it can."""
    if not org or org.status != "active":
        return "The organisation is suspended"
    if org.billing_status == "cancelled":
        return "The subscription has ended"
    if org.scan_limit is not None and await scans_this_month(db, org.id) >= org.scan_limit:
        return f"All {org.scan_limit} scans for this month are used"
    return None


def build_job(schedule: ScanSchedule, now: datetime) -> AuditJob:
    return AuditJob(
        created_by=schedule.created_by, organization_id=schedule.organization_id, source_type=schedule.source_type,
        target_url=schedule.target if schedule.source_type == "web" else None,
        repo_url=schedule.target if schedule.source_type == "repo" else None,
        outputs=schedule.outputs, depth=schedule.depth, ownership_confirmed_at=now, started_at=now,
        trigger={"kind": "schedule", "schedule_id": schedule.id},
    )


async def run_one(db: AsyncSession, schedule: ScanSchedule, now: datetime) -> AuditJob | None:
    """Start this schedule's scan, or note why it was skipped. The caller commits and launches."""
    reason = await blocked(db, await db.get(Organization, schedule.organization_id))
    schedule.last_run_at = now
    if reason:
        schedule.last_note = f"Skipped: {reason}"
        return None
    job = build_job(schedule, now)
    db.add(job)
    await db.flush()
    schedule.last_audit_id, schedule.last_note = job.id, None
    return job


async def run_due(now: datetime | None = None) -> list[str]:
    """Start every schedule that is due. Safe to call from several servers at once: each schedule is claimed first."""
    now = now or datetime.now(timezone.utc)
    started: list[str] = []
    async with AsyncSessionLocal() as db:
        due = (await db.execute(select(ScanSchedule).where(ScanSchedule.active.is_(True), ScanSchedule.next_run_at <= now))).scalars().all()
        for schedule in due:
            claimed = await db.execute(
                update(ScanSchedule).where(ScanSchedule.id == schedule.id, ScanSchedule.next_run_at == schedule.next_run_at)
                .values(next_run_at=next_after(schedule.next_run_at, schedule.frequency, now))
            )
            if claimed.rowcount != 1:
                continue
            await db.refresh(schedule)
            job = await run_one(db, schedule, now)
            await db.commit()
            if job:
                started.append(job.id)
    for job_id in started:
        scan_control.launch(job_id)
    return started


async def ticker(every: int = 60) -> None:
    """Runs for the life of the server."""
    while True:
        try:
            await run_due()
        except Exception:
            log.exception("scheduled scans could not be checked")
        await asyncio.sleep(every)
