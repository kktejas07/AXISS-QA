"""Scans that repeat on a timetable."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.database import get_db
from app.models.automation import ScanSchedule
from app.services import scan_control, schedules
from app.services.code_auditor import SourceError, parse_repo_url

router = APIRouter(prefix="/schedules", tags=["schedules"])
MAX_PER_ORG = 20
OUTPUTS = {"web": ["security", "manual", "playwright"], "repo": ["security", "manual"]}


class ScheduleIn(BaseModel):
    source_type: Literal["web", "repo"]
    target: str
    frequency: Literal["daily", "weekly", "monthly"]
    outputs: list[str] = ["security"]
    depth: Literal["quick", "standard", "deep"] = "standard"
    ownership_confirmed: bool = False


class ScheduleChange(BaseModel):
    frequency: Literal["daily", "weekly", "monthly"] | None = None
    active: bool | None = None


class ScheduleOut(BaseModel):
    id: str
    source_type: str
    target: str
    frequency: str
    outputs: list[str]
    depth: str
    active: bool
    next_run_at: datetime
    last_run_at: datetime | None
    last_audit_id: str | None
    last_note: str | None

    model_config = {"from_attributes": True}


async def _get(db: AsyncSession, ctx: OrgContext, schedule_id: str) -> ScanSchedule:
    row = (await db.execute(select(ScanSchedule).where(ScanSchedule.id == schedule_id, ScanSchedule.organization_id == ctx.org.id))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Schedule not found")
    return row


@router.get("", response_model=list[ScheduleOut])
async def list_schedules(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    return (await db.execute(select(ScanSchedule).where(ScanSchedule.organization_id == ctx.org.id).order_by(ScanSchedule.created_at.desc()))).scalars().all()


@router.post("", response_model=ScheduleOut, status_code=201)
async def create_schedule(body: ScheduleIn, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("scan.run")
    if ctx.via_api_key:
        raise HTTPException(403, "Schedules are set up by a person, not with an API key")
    if not body.ownership_confirmed:
        raise HTTPException(400, "Confirm that you own this app or have permission to test it")
    target = body.target.strip()
    if body.source_type == "repo":
        try:
            target, _ = parse_repo_url(target)
        except SourceError as e:
            raise HTTPException(422, str(e))
    elif not target.startswith(("http://", "https://")) or len(target) > 2048:
        raise HTTPException(422, "Enter a full web address starting with http:// or https://")
    allowed = OUTPUTS[body.source_type]
    outputs = [o for o in allowed if o in set(body.outputs)]
    if not outputs or set(body.outputs) - set(allowed):
        raise HTTPException(422, f"Choose from: {', '.join(allowed)}")
    existing = (await db.execute(select(ScanSchedule).where(ScanSchedule.organization_id == ctx.org.id))).scalars().all()
    if len(existing) >= MAX_PER_ORG:
        raise HTTPException(400, f"An organisation can have {MAX_PER_ORG} schedules. Delete one to add another.")
    if any(s.source_type == body.source_type and s.target == target for s in existing):
        raise HTTPException(409, "There is already a schedule for that")
    now = datetime.now(timezone.utc)
    row = ScanSchedule(organization_id=ctx.org.id, created_by=ctx.user.id, source_type=body.source_type, target=target,
                       outputs=outputs, depth=body.depth, frequency=body.frequency, next_run_at=schedules.advance(now, body.frequency))
    db.add(row)
    await db.flush()
    return row


@router.patch("/{schedule_id}", response_model=ScheduleOut)
async def change_schedule(schedule_id: str, body: ScheduleChange, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("scan.run")
    row = await _get(db, ctx, schedule_id)
    now = datetime.now(timezone.utc)
    if body.frequency and body.frequency != row.frequency:
        row.frequency, row.next_run_at = body.frequency, schedules.advance(now, body.frequency)
    if body.active is not None and body.active != row.active:
        row.active = body.active
        if body.active:
            row.next_run_at = schedules.next_after(row.next_run_at, row.frequency, now)
    await db.flush()
    return row


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("scan.run")
    await db.delete(await _get(db, ctx, schedule_id))


@router.post("/{schedule_id}/run", response_model=ScheduleOut)
async def run_now(schedule_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Start this schedule's scan now, without changing when it next runs by itself."""
    ctx.require("scan.run")
    row = await _get(db, ctx, schedule_id)
    job = await schedules.run_one(db, row, datetime.now(timezone.utc))
    if not job:
        raise HTTPException(403, (row.last_note or "").removeprefix("Skipped: ") or "The scan could not be started")
    await db.commit()
    await db.refresh(row)
    scan_control.launch(job.id)
    return row
