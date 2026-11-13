"""
A scan in the app is an "audit job". The flow is:

POST /api/v1/audits                     — step 1: say what is being tested (draft, nothing runs)
POST /api/v1/audits/{id}/upload         — step 1, mobile: attach the .apk or .ipa
POST /api/v1/audits/{id}/start          — step 2: choose outputs and depth, confirm permission, run
GET  /api/v1/audits/{id}                — status, per-step progress and results
GET  /api/v1/audits/{id}/stream         — the same progress as server-sent events
GET  /api/v1/audits/{id}/export/{kind}  — download: report, test-cases, playwright, appium, results
GET  /api/v1/audits                     — the user's scans, newest first
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.core.storage import storage_path
from app.models.audit_job import AuditJob, AuditStatus
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/audits", tags=["audits"])

# Keep a reference to running audits so the event loop does not drop them mid-run.
_running: set[asyncio.Task] = set()


def _launch(job_id: str) -> None:
    from app.services.audit_orchestrator import run_audit

    task = asyncio.create_task(run_audit(job_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AuditCreate(BaseModel):
    source_type: Literal["web", "android", "ios"] = "web"
    target_url: str | None = None
    app_name: str | None = None
    mobile_url: str | None = None   # Play Store / App Store URL
    # True keeps the original one-call behaviour: run everything straight away.
    autostart: bool = True


class AuditStart(BaseModel):
    outputs: list[str]
    depth: Literal["quick", "standard", "deep"] = "standard"
    ownership_confirmed: bool = False


class AuditOut(BaseModel):
    id: str
    label: str
    source_type: str
    target_url: str | None
    app_name: str | None
    mobile_url: str | None
    source_filename: str | None
    outputs: list[str] | None
    allowed_outputs: list[str]
    depth: str
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
    exports: list[str]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class AuditDetailOut(AuditOut):
    tier1_result: dict | None
    tier2_result: dict | None
    tier3_result: dict | None
    tier4_result: dict | None
    tier5_result: dict | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_job(audit_id: str, db: AsyncSession, user: User) -> AuditJob:
    result = await db.execute(select(AuditJob).where(AuditJob.id == audit_id, AuditJob.created_by == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Scan not found")
    return job


def _is_web_address(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


async def _save_upload(file: UploadFile, audit_id: str, suffix: str) -> str:
    """Stream the upload to disk, refusing empty files and anything over MAX_UPLOAD_MB."""
    path = storage_path("uploads", f"{audit_id}{suffix}")
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    try:
        with open(path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File is larger than {settings.MAX_UPLOAD_MB} MB")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "The file is empty")
    except HTTPException:
        if os.path.exists(path):
            os.remove(path)
        raise
    return path


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=AuditOut, status_code=201)
async def create_audit(
    body: AuditCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record what is being tested. Runs at once only when autostart is true and nothing else is needed."""
    target_url = body.target_url.strip() if body.target_url else None
    if body.source_type == "web":
        if not _is_web_address(target_url):
            raise HTTPException(422, "Enter a full web address starting with http:// or https://")
    else:
        target_url = None
    if body.mobile_url and not _is_web_address(body.mobile_url):
        raise HTTPException(422, "The app store link must start with http:// or https://")

    job = AuditJob(
        created_by=user.id,
        source_type=body.source_type,
        target_url=target_url,
        app_name=(body.app_name or "").strip() or None,
        mobile_url=body.mobile_url,
    )
    # A mobile job needs its build uploaded first, so it always starts as a draft.
    autostart = body.autostart and (body.source_type == "web" or bool(body.mobile_url))
    if autostart:
        job.outputs = None  # run everything, as before
        job.started_at = datetime.now(timezone.utc)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    if autostart:
        _launch(job.id)
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
    return await _get_job(audit_id, db, user)


@router.post("/{audit_id}/upload", response_model=AuditOut)
async def upload_build(
    audit_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Attach an Android .apk or iOS .ipa to a scan that has not started yet."""
    job = await _get_job(audit_id, db, user)
    if job.started_at:
        raise HTTPException(409, "This scan has already started. Create a new scan to test another build.")

    name = os.path.basename(file.filename or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in (".apk", ".ipa"):
        raise HTTPException(415, "Upload an Android .apk or an iOS .ipa file")
    expected = {"android": ".apk", "ios": ".ipa"}.get(job.source_type)
    if expected and ext != expected:
        raise HTTPException(415, f"This scan is for {job.source_type}. Upload a {expected} file.")

    path = await _save_upload(file, audit_id, ext)
    if ext == ".apk":
        job.apk_path, job.ipa_path = path, None
    else:
        job.ipa_path, job.apk_path = path, None
    job.source_filename = name[:255]
    await db.commit()
    await db.refresh(job)
    return job


# The original two endpoints, kept so existing clients keep working.
@router.post("/{audit_id}/upload-apk", response_model=AuditOut, include_in_schema=False)
async def upload_apk(audit_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await upload_build(audit_id, file, db, user)


@router.post("/{audit_id}/upload-ipa", response_model=AuditOut, include_in_schema=False)
async def upload_ipa(audit_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await upload_build(audit_id, file, db, user)


@router.post("/{audit_id}/start", response_model=AuditOut)
async def start_audit(
    audit_id: str,
    body: AuditStart,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Step 2: record what the user wants and begin. Refuses without their confirmation of permission."""
    job = await _get_job(audit_id, db, user)
    if job.started_at:
        raise HTTPException(409, "This scan has already started")
    if not body.ownership_confirmed:
        raise HTTPException(400, "Confirm that you own this app or have permission to test it")

    allowed = job.allowed_outputs
    outputs = [o for o in allowed if o in set(body.outputs)]  # de-duplicated, in a stable order
    unknown = sorted(set(body.outputs) - set(allowed))
    if unknown:
        raise HTTPException(422, f"Not available for this app: {', '.join(unknown)}. Choose from: {', '.join(allowed)}")
    if not outputs:
        raise HTTPException(422, "Choose at least one output")
    if job.source_type in ("android", "ios") and not job.has_mobile_input:
        raise HTTPException(400, "Upload the app build before starting")

    now = datetime.now(timezone.utc)
    job.outputs = outputs
    job.depth = body.depth
    job.ownership_confirmed_at = now
    job.started_at = now
    await db.commit()
    await db.refresh(job)

    _launch(job.id)
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
        for _ in range(300):  # max 10 min
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


def _attachment(content: str, media_type: str, filename: str) -> Response:
    return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{audit_id}/export/{kind}")
async def export_audit(
    audit_id: str,
    kind: Literal["report", "test-cases", "playwright", "appium", "results"],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download one output of a scan. job.exports lists the kinds that exist."""
    job = await _get_job(audit_id, db, user)
    short = audit_id[:8]
    if kind not in job.exports:
        raise HTTPException(404, "That download is not available for this scan yet")

    if kind == "report":
        return FileResponse(job.report_pdf_path, media_type="application/pdf", filename=f"wiseflow-report-{short}.pdf")
    if kind == "test-cases":
        return _attachment(job.tier4_result["jira_csv"], "text/csv", f"wiseflow-test-cases-{short}.csv")
    if kind == "playwright":
        return _attachment(job.tier1_result["playwright_tests"], "text/x-python", f"test_web_{short}.py")
    if kind == "appium":
        return _attachment(job.tier2_result["appium_tests"], "text/x-python", f"test_mobile_{short}.py")
    data = {
        "id": job.id,
        "app": job.label,
        "source_type": job.source_type,
        "target_url": job.target_url,
        "outputs": job.outputs,
        "depth": job.depth,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "risk_score": job.risk_score,
        "critical_count": job.critical_count,
        "high_count": job.high_count,
        "executive_summary": job.executive_summary,
        "web": job.tier1_result,
        "mobile": job.tier2_result,
        "security": job.tier3_result,
        "manual_test_cases": (job.tier4_result or {}).get("test_cases"),
    }
    return _attachment(json.dumps(data, indent=2, default=str), "application/json", f"wiseflow-results-{short}.json")


@router.get("/{audit_id}/download", include_in_schema=False)
async def download_audit_report(audit_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Original PDF download address, kept for existing links."""
    return await export_audit(audit_id, "report", db, user)
