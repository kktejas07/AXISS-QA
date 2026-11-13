"""
A scan in the app is an "audit job". The flow is:

POST /api/v1/audits                     — step 1: say what is being tested (draft, nothing runs)
POST /api/v1/audits/{id}/upload         — step 1: attach the .apk or .ipa, or a .zip of source code
POST /api/v1/audits/{id}/start          — step 2: choose outputs and depth, confirm permission, run
POST /api/v1/audits/{id}/stop           — stop a scan that is queued or running
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
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select

from app.core.config import settings
from app.core.database import get_db
from app.core.secrets import encrypt
from app.core.security import decode_token
from app.core.storage import storage_path
from app.models.audit_job import AuditJob, AuditStatus
from app.models.user import User
from app.api.deps import OrgContext, get_org_context
from app.services.code_auditor import SourceError, parse_repo_url
from app.services import api_spec_auditor, scan_control
from app.services.orgs import scans_this_month

router = APIRouter(prefix="/audits", tags=["audits"])

def _launch(job_id: str) -> None:
    scan_control.launch(job_id)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AuditCreate(BaseModel):
    source_type: Literal["web", "android", "ios", "code", "repo", "api"] = "web"
    target_url: str | None = None
    repo_url: str | None = None     # public GitHub, GitLab or Bitbucket link, for source_type "repo"
    app_name: str | None = None
    mobile_url: str | None = None   # Play Store / App Store URL
    # True keeps the original one-call behaviour: run everything straight away.
    autostart: bool = True


class LoginDetails(BaseModel):
    """The app's own sign-in page and a test account, so pages behind the login are scanned too."""
    url: str = Field(max_length=2048)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class AuditStart(BaseModel):
    outputs: list[str]
    depth: Literal["quick", "standard", "deep"] = "standard"
    ownership_confirmed: bool = False
    login: LoginDetails | None = None


class AuditOut(BaseModel):
    id: str
    label: str
    source_type: str
    target_url: str | None
    app_name: str | None
    mobile_url: str | None
    repo_url: str | None
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

def _visible(org_id: str | None, user_id: str):
    """Scans the user may see: their organisation's, plus their own from before organisations existed."""
    return or_(
        AuditJob.organization_id == org_id,
        and_(AuditJob.organization_id.is_(None), AuditJob.created_by == user_id),
    )


async def _get_job(audit_id: str, db: AsyncSession, ctx: OrgContext) -> AuditJob:
    result = await db.execute(select(AuditJob).where(AuditJob.id == audit_id, _visible(ctx.org.id, ctx.user.id)))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Scan not found")
    return job


def _is_web_address(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


async def _check_org_can_scan(db: AsyncSession, ctx: OrgContext) -> None:
    """Refuse to start when the organisation is suspended or has used its scans for the month."""
    org = ctx.org
    if org.status != "active":
        raise HTTPException(403, "This organisation is suspended, so new scans cannot start. Contact support.")
    if org.billing_provider and org.billing_status == "cancelled":
        raise HTTPException(403, "Your subscription has ended, so new scans cannot start. An owner can renew it under Settings.")
    if org.scan_limit is not None and await scans_this_month(db, org.id) >= org.scan_limit:
        raise HTTPException(403, f"Your organisation has used all {org.scan_limit} scans for this month.")


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
    ctx: OrgContext = Depends(get_org_context),
):
    """Record what is being tested. Runs at once only when autostart is true and nothing else is needed."""
    ctx.require("scan.run")
    target_url = body.target_url.strip() if body.target_url else None
    if body.source_type == "web":
        if not _is_web_address(target_url):
            raise HTTPException(422, "Enter a full web address starting with http:// or https://")
    elif body.source_type == "api":
        # Optional: where the API runs, to probe it as well as reading its description.
        if target_url and not _is_web_address(target_url):
            raise HTTPException(422, "The API's address must start with http:// or https://")
    else:
        target_url = None
    if body.mobile_url and not _is_web_address(body.mobile_url):
        raise HTTPException(422, "The app store link must start with http:// or https://")
    repo_url = None
    if body.source_type == "repo":
        try:
            repo_url, _ = parse_repo_url(body.repo_url or "")
        except SourceError as e:
            raise HTTPException(422, str(e))

    job = AuditJob(
        created_by=ctx.user.id,
        organization_id=ctx.org.id,
        source_type=body.source_type,
        target_url=target_url,
        app_name=(body.app_name or "").strip() or None,
        mobile_url=body.mobile_url,
        repo_url=repo_url,
    )
    # A mobile job needs its build uploaded first, so it always starts as a draft.
    autostart = body.autostart and (body.source_type == "web" or bool(body.mobile_url))
    if autostart:
        await _check_org_can_scan(db, ctx)
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
    ctx: OrgContext = Depends(get_org_context),
):
    result = await db.execute(
        select(AuditJob)
        .where(_visible(ctx.org.id, ctx.user.id))
        .order_by(AuditJob.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{audit_id}", response_model=AuditDetailOut)
async def get_audit(
    audit_id: str,
    db: AsyncSession = Depends(get_db),
    ctx: OrgContext = Depends(get_org_context),
):
    return await _get_job(audit_id, db, ctx)


@router.post("/{audit_id}/upload", response_model=AuditOut)
async def upload_build(
    audit_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    ctx: OrgContext = Depends(get_org_context),
):
    """Attach an Android .apk, an iOS .ipa or a .zip of source code to a scan that has not started yet."""
    ctx.require("scan.run")
    job = await _get_job(audit_id, db, ctx)
    if job.started_at:
        raise HTTPException(409, "This scan has already started. Create a new scan to test another build.")

    name = os.path.basename(file.filename or "")
    ext = os.path.splitext(name)[1].lower()
    if job.source_type == "code":
        if ext != ".zip":
            raise HTTPException(415, "Upload the source code as a .zip file")
        job.source_path = await _save_upload(file, audit_id, ext)
        job.source_filename = name[:255]
        await db.commit()
        await db.refresh(job)
        return job
    if job.source_type == "api":
        if ext not in (".json", ".yaml", ".yml"):
            raise HTTPException(415, "Upload the OpenAPI or Swagger file as .json, .yaml or .yml")
        try:
            about = api_spec_auditor.overview(api_spec_auditor.parse(await file.read(api_spec_auditor.MAX_BYTES + 1)))
        except api_spec_auditor.SpecError as e:
            raise HTTPException(422, str(e))
        await file.seek(0)
        job.source_path = await _save_upload(file, audit_id, ext)
        job.source_filename = name[:255]
        job.app_name = job.app_name or about["title"]
        await db.commit()
        await db.refresh(job)
        return job
    if job.source_type == "repo":
        raise HTTPException(415, "This scan reads a repository link, so there is nothing to upload")
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
async def upload_apk(audit_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    return await upload_build(audit_id, file, db, ctx)


@router.post("/{audit_id}/upload-ipa", response_model=AuditOut, include_in_schema=False)
async def upload_ipa(audit_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    return await upload_build(audit_id, file, db, ctx)


@router.post("/{audit_id}/start", response_model=AuditOut)
async def start_audit(
    audit_id: str,
    body: AuditStart,
    db: AsyncSession = Depends(get_db),
    ctx: OrgContext = Depends(get_org_context),
):
    """Step 2: record what the user wants and begin. Refuses without their confirmation of permission."""
    ctx.require("scan.run")
    job = await _get_job(audit_id, db, ctx)
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
    if job.source_type == "code" and not job.source_path:
        raise HTTPException(400, "Upload the source code before starting")
    if job.source_type == "api" and not job.source_path:
        raise HTTPException(400, "Upload the API description before starting")
    login = None
    if body.login:
        if job.source_type != "web":
            raise HTTPException(422, "Sign-in details can only be used when scanning a website")
        site, page = urlparse(job.target_url or ""), urlparse(body.login.url.strip())
        if (page.scheme, page.netloc) != (site.scheme, site.netloc):
            raise HTTPException(422, "The sign-in page must be on the site being scanned, so the password is not sent anywhere else")
        login = encrypt(json.dumps({"url": body.login.url.strip(), "username": body.login.username, "password": body.login.password}))
    await _check_org_can_scan(db, ctx)

    now = datetime.now(timezone.utc)
    job.outputs = outputs
    job.depth = body.depth
    job.ownership_confirmed_at = now
    job.started_at = now
    job.login_encrypted = login
    await db.commit()
    await db.refresh(job)

    _launch(job.id)
    return job


@router.post("/{audit_id}/stop", response_model=AuditOut)
async def stop_audit(audit_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Stop a scan that is queued or running. Results from steps that already finished are kept."""
    ctx.require("scan.run")
    job = await _get_job(audit_id, db, ctx)
    try:
        await scan_control.stop(db, job, f"Stopped by {ctx.user.full_name}")
    except scan_control.NotActive:
        raise HTTPException(409, "This scan is not running")
    await db.commit()
    await db.refresh(job)
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
                viewer = await db.get(User, user_id)
                res = await db.execute(
                    select(AuditJob).where(AuditJob.id == audit_id, _visible(viewer.organization_id if viewer else None, user_id))
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
    ctx: OrgContext = Depends(get_org_context),
):
    """Download one output of a scan. job.exports lists the kinds that exist."""
    job = await _get_job(audit_id, db, ctx)
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
        "repository": job.repo_url,
        "outputs": job.outputs,
        "depth": job.depth,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "risk_score": job.risk_score,
        "critical_count": job.critical_count,
        "high_count": job.high_count,
        "executive_summary": job.executive_summary,
        "web": None if job.is_code else job.tier1_result,
        "code": job.tier1_result if job.is_code else None,
        "mobile": job.tier2_result,
        "security": job.tier3_result,
        "manual_test_cases": (job.tier4_result or {}).get("test_cases"),
    }
    return _attachment(json.dumps(data, indent=2, default=str), "application/json", f"wiseflow-results-{short}.json")


@router.get("/{audit_id}/download", include_in_schema=False)
async def download_audit_report(audit_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Original PDF download address, kept for existing links."""
    return await export_audit(audit_id, "report", db, ctx)
