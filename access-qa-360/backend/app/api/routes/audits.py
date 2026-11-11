"""
POST /api/v1/audits         — create + kick off a full 5-tier audit
GET  /api/v1/audits/{id}    — poll audit status + tier results
GET  /api/v1/audits/{id}/stream  — SSE real-time progress
GET  /api/v1/audits         — list audits for the current user
GET  /api/v1/audits/{id}/download — download the unified PDF report
POST /api/v1/audits/{id}/upload-apk  — upload an APK file
POST /api/v1/audits/{id}/upload-ipa  — upload an IPA file
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.audit_job import AuditJob, AuditStatus
from app.models.user import User
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import decode_token

router = APIRouter(prefix="/audits", tags=["audits"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AuditCreate(BaseModel):
    target_url: str
    app_name: str | None = None
    mobile_url: str | None = None   # Play Store / App Store URL


class AuditOut(BaseModel):
    id: str
    target_url: str
    app_name: str | None
    mobile_url: str | None
    status: str
    progress: int
    tier1_status: str
    tier2_status: str
    tier3_status: str
    tier4_status: str
    tier5_status: str
    risk_score: int | None
    coverage_pct: int | None
    critical_count: int
    high_count: int
    total_test_cases: int
    total_pages_audited: int
    executive_summary: str | None
    report_pdf_path: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AuditDetailOut(AuditOut):
    tier1_result: dict | None
    tier2_result: dict | None
    tier3_result: dict | None
    tier4_result: dict | None
    tier5_result: dict | None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=AuditOut, status_code=201)
async def create_audit(
    body: AuditCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new audit job and start all 5 tiers in the background."""
    job = AuditJob(
        created_by=user.id,
        target_url=body.target_url,
        app_name=body.app_name,
        mobile_url=body.mobile_url,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Fire-and-forget — the orchestrator updates the DB throughout
    from app.services.audit_orchestrator import run_audit
    asyncio.create_task(run_audit(job.id))

    return job


@router.get("", response_model=list[AuditOut])
async def list_audits(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AuditJob)
        .where(AuditJob.created_by == user.id)
        .order_by(AuditJob.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{audit_id}", response_model=AuditDetailOut)
async def get_audit(
    audit_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AuditJob).where(AuditJob.id == audit_id, AuditJob.created_by == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Audit not found")
    return job


@router.get("/{audit_id}/stream")
async def stream_audit_progress(
    audit_id: str,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint — streams progress events until the job reaches a terminal state."""
    user_id = decode_token(token or "") if token else None
    if not user_id:
        raise HTTPException(401, "Unauthorized")

    async def _event_generator():
        terminal = {AuditStatus.completed.value, AuditStatus.failed.value, AuditStatus.partial.value}
        for _ in range(300):  # max 5 min
            async with db.begin():
                res = await db.execute(
                    select(AuditJob).where(AuditJob.id == audit_id, AuditJob.created_by == user_id)
                )
                job = res.scalar_one_or_none()

            if not job:
                yield "event: error\ndata: {\"error\": \"not_found\"}\n\n"
                break

            payload = {
                "progress": job.progress,
                "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
                "tier1_status": job.tier1_status,
                "tier2_status": job.tier2_status,
                "tier3_status": job.tier3_status,
                "tier4_status": job.tier4_status,
                "tier5_status": job.tier5_status,
            }
            yield f"event: progress\ndata: {json.dumps(payload)}\n\n"

            status_val = job.status.value if hasattr(job.status, 'value') else str(job.status)
            if status_val in terminal:
                yield f"event: done\ndata: {json.dumps({'audit_id': audit_id, 'status': status_val})}\n\n"
                break

            await asyncio.sleep(2)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{audit_id}/download")
async def download_audit_report(
    audit_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download the unified PDF report."""
    result = await db.execute(
        select(AuditJob).where(AuditJob.id == audit_id, AuditJob.created_by == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Audit not found")
    if not job.report_pdf_path or not os.path.exists(job.report_pdf_path):
        raise HTTPException(404, "Report not yet generated")
    return FileResponse(
        job.report_pdf_path,
        media_type="application/pdf",
        filename=f"audit_{audit_id[:8]}.pdf",
    )


@router.post("/{audit_id}/upload-apk", response_model=AuditOut)
async def upload_apk(
    audit_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload an APK and trigger/re-trigger the mobile tier."""
    result = await db.execute(
        select(AuditJob).where(AuditJob.id == audit_id, AuditJob.created_by == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Audit not found")

    # Save APK to temp location
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".apk", prefix=f"audit_{audit_id}_")
    os.close(fd)
    with open(path, "wb") as f:
        content = await file.read()
        f.write(content)

    job.apk_path = path
    job.tier2_status = "pending"
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{audit_id}/upload-ipa", response_model=AuditOut)
async def upload_ipa(
    audit_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload an IPA and trigger/re-trigger the mobile tier."""
    result = await db.execute(
        select(AuditJob).where(AuditJob.id == audit_id, AuditJob.created_by == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Audit not found")

    import tempfile
    fd, path = tempfile.mkstemp(suffix=".ipa", prefix=f"audit_{audit_id}_")
    os.close(fd)
    with open(path, "wb") as f:
        content = await file.read()
        f.write(content)

    job.ipa_path = path
    job.tier2_status = "pending"
    await db.commit()
    await db.refresh(job)
    return job
