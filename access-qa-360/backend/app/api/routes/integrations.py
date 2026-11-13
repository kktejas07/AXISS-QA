"""
API keys for pipelines, the Jira connection, and sending findings to Jira.

GET/POST   /api/v1/org/api-keys            list, create (the key is shown once)
DELETE     /api/v1/org/api-keys/{id}       revoke
GET/PUT/DELETE /api/v1/org/integrations/jira
GET/POST   /api/v1/audits/{id}/issues      issues already created; create one from a finding
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.config import settings
from app.core.database import get_db
from app.core.secrets import decrypt, encrypt
from app.models.audit_job import AuditJob
from app.models.integration import ApiKey, Integration, TrackerIssue
from app.models.user import User
from app.services import jira
from app.services.api_keys import new_api_key

router = APIRouter(tags=["integrations"])


# ---- API keys ---------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_by_email: str | None = None
    created_at: datetime
    last_used_at: datetime | None
    # Only in the answer to creating a key. It cannot be shown again.
    key: str | None = None


@router.get("/org/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    rows = await db.execute(
        select(ApiKey, User.email).join(User, User.id == ApiKey.created_by)
        .where(ApiKey.organization_id == ctx.org.id, ApiKey.revoked_at.is_(None)).order_by(ApiKey.created_at.desc())
    )
    return [
        ApiKeyOut(id=k.id, name=k.name, prefix=k.prefix, created_by_email=email, created_at=k.created_at, last_used_at=k.last_used_at)
        for k, email in rows.all()
    ]


@router.post("/org/api-keys", response_model=ApiKeyOut, status_code=201)
async def create_api_key(body: ApiKeyCreate, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Create a key that can view results and run scans for this organisation, acting as the person who made it."""
    ctx.require("org.edit")
    active = (await db.execute(select(ApiKey).where(ApiKey.organization_id == ctx.org.id, ApiKey.revoked_at.is_(None)))).scalars().all()
    if len(active) >= 20:
        raise HTTPException(400, "This organisation already has 20 API keys. Revoke one you no longer use.")
    token, prefix, key_hash = new_api_key()
    key = ApiKey(organization_id=ctx.org.id, created_by=ctx.user.id, name=body.name.strip(), prefix=prefix, key_hash=key_hash)
    db.add(key)
    await db.flush()
    await db.refresh(key)
    return ApiKeyOut(id=key.id, name=key.name, prefix=key.prefix, created_by_email=ctx.user.email, created_at=key.created_at, last_used_at=None, key=token)


@router.delete("/org/api-keys/{key_id}", status_code=204)
async def revoke_api_key(key_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    key = (
        await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == ctx.org.id, ApiKey.revoked_at.is_(None)))
    ).scalar_one_or_none()
    if not key:
        raise HTTPException(404, "API key not found")
    key.revoked_at = datetime.now(timezone.utc)


# ---- Jira -------------------------------------------------------------------

class JiraSave(BaseModel):
    base_url: str
    email: EmailStr
    api_token: str = Field(min_length=8, max_length=500)
    project_key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{1,19}$")
    issue_type: str = Field(default="Bug", min_length=1, max_length=60)


class JiraOut(BaseModel):
    connected: bool
    base_url: str | None = None
    email: str | None = None
    project_key: str | None = None
    project_name: str | None = None
    issue_type: str | None = None


async def _jira(db: AsyncSession, org_id: str) -> Integration | None:
    return (await db.execute(select(Integration).where(Integration.organization_id == org_id, Integration.kind == "jira"))).scalar_one_or_none()


def _jira_out(row: Integration | None) -> JiraOut:
    if not row:
        return JiraOut(connected=False)
    return JiraOut(connected=True, **{k: row.config.get(k) for k in ("base_url", "email", "project_key", "project_name", "issue_type")})


@router.get("/org/integrations/jira", response_model=JiraOut)
async def get_jira(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Everyone in the organisation can see whether Jira is connected; the token is never returned."""
    return _jira_out(await _jira(db, ctx.org.id))


@router.put("/org/integrations/jira", response_model=JiraOut)
async def save_jira(body: JiraSave, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Connect Jira Cloud. The details are checked against Jira before they are saved."""
    ctx.require("org.edit")
    try:
        base_url = jira.clean_base_url(body.base_url)
        project_key = body.project_key.upper()
        checked = await jira.check_connection(base_url, body.email, body.api_token, project_key, body.issue_type)
    except jira.JiraError as e:
        raise HTTPException(400, str(e))
    config = {"base_url": base_url, "email": body.email, "project_key": project_key, "project_name": checked["project_name"], "issue_type": body.issue_type}
    row = await _jira(db, ctx.org.id)
    if row:
        row.config, row.secret_encrypted = config, encrypt(body.api_token)
    else:
        row = Integration(organization_id=ctx.org.id, kind="jira", config=config, secret_encrypted=encrypt(body.api_token), created_by=ctx.user.id)
        db.add(row)
    await db.flush()
    return _jira_out(row)


@router.delete("/org/integrations/jira", status_code=204)
async def disconnect_jira(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    row = await _jira(db, ctx.org.id)
    if row:
        await db.delete(row)


# ---- findings to issues -----------------------------------------------------

class IssueCreate(BaseModel):
    source: Literal["security", "mobile"]
    index: int = Field(ge=0)


class IssueOut(BaseModel):
    finding_ref: str
    issue_key: str
    issue_url: str


async def _job(db: AsyncSession, ctx: OrgContext, audit_id: str) -> AuditJob:
    job = (
        await db.execute(
            select(AuditJob).where(
                AuditJob.id == audit_id,
                or_(AuditJob.organization_id == ctx.org.id, and_(AuditJob.organization_id.is_(None), AuditJob.created_by == ctx.user.id)),
            )
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Scan not found")
    return job


@router.get("/audits/{audit_id}/issues", response_model=list[IssueOut])
async def list_issues(audit_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    job = await _job(db, ctx, audit_id)
    return (await db.execute(select(TrackerIssue).where(TrackerIssue.audit_id == job.id))).scalars().all()


@router.post("/audits/{audit_id}/issues", response_model=IssueOut, status_code=201)
async def create_issue(audit_id: str, body: IssueCreate, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Create a Jira issue from one finding. A finding gets one issue; asking again returns the same one."""
    ctx.require("scan.run")
    job = await _job(db, ctx, audit_id)
    ref = f"{body.source}:{body.index}"
    existing = (await db.execute(select(TrackerIssue).where(TrackerIssue.audit_id == job.id, TrackerIssue.finding_ref == ref))).scalar_one_or_none()
    if existing:
        return existing

    findings = (job.tier3_result or {}).get("findings", []) if body.source == "security" else (job.tier2_result or {}).get("security_flags", [])
    if body.index >= len(findings):
        raise HTTPException(404, "That finding is not part of this scan")
    finding = dict(findings[body.index])
    if body.source == "mobile":
        finding.setdefault("affected_url", job.source_filename or "Mobile build")

    row = await _jira(db, ctx.org.id)
    if not row:
        raise HTTPException(400, "Jira is not connected. An owner or admin can connect it in Settings.")
    token = decrypt(row.secret_encrypted)
    if not token:
        raise HTTPException(400, "The saved Jira token can no longer be read. Connect Jira again in Settings.")
    cfg = row.config
    try:
        fields = jira.issue_fields(finding, job.label, f"{settings.APP_URL.rstrip('/')}/audits/{job.id}?tab=security", cfg["project_key"], cfg["issue_type"])
        key, url = await jira.create_issue(cfg["base_url"], cfg["email"], token, fields)
    except jira.JiraError as e:
        raise HTTPException(502, str(e))
    issue = TrackerIssue(audit_id=job.id, finding_ref=ref, issue_key=key, issue_url=url, created_by=ctx.user.id)
    db.add(issue)
    await db.flush()
    return issue
