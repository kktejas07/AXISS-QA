"""Super admin console: platform-wide numbers and user management.

Every route here requires the super_admin role (see require_super_admin).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio

from app.api.deps import require_super_admin
from app.core import platform
from app.core.config import settings
from app.core.providers import PROVIDERS
from app.core.database import get_db
from app.models.audit_job import AuditJob, AuditStatus
from app.models.organization import AdminAuditLog, Organization
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.user import ROLE_SUPER_ADMIN, User
from app.models.vulnerability import Severity, VulnStatus, Vulnerability
from app.schemas.admin import (
    AdminOrgDetail, AdminOrgMember, AdminOrgOut, AdminOrgUpdate, AdminOverview, AdminScanOut, AdminUserOut, AdminUserUpdate, AuditLogOut,
)
from app.services import password_reset
from app.services.orgs import DEFAULT_SEATS, by_seniority, log_admin_action, member_count, scans_this_month

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_super_admin)])

RUNNING = [ScanStatus.crawling, ScanStatus.scanning, ScanStatus.analyzing]


def _value(enum_or_str) -> str:
    return getattr(enum_or_str, "value", enum_or_str)


async def _count(db: AsyncSession, model, *where) -> int:
    return (await db.execute(select(func.count()).select_from(model).where(*where))).scalar() or 0


@router.get("/overview", response_model=AdminOverview)
async def overview(db: AsyncSession = Depends(get_db)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    open_vulns = {s.value: 0 for s in Severity}
    rows = await db.execute(
        select(Vulnerability.severity, func.count())
        .where(Vulnerability.status.in_([VulnStatus.open, VulnStatus.confirmed]))
        .group_by(Vulnerability.severity)
    )
    for severity, count in rows.all():
        open_vulns[_value(severity)] = count

    started = AuditJob.started_at.is_not(None)  # drafts that never ran are not scans yet

    return AdminOverview(
        users_total=await _count(db, User),
        users_active=await _count(db, User, User.is_active.is_(True)),
        super_admins=await _count(db, User, User.role == ROLE_SUPER_ADMIN),
        projects_total=await _count(db, Project),
        scans_total=await _count(db, Scan) + await _count(db, AuditJob, started),
        scans_today=await _count(db, Scan, Scan.created_at >= today) + await _count(db, AuditJob, AuditJob.started_at >= today),
        scans_running=await _count(db, Scan, Scan.status.in_(RUNNING))
        + await _count(db, AuditJob, AuditJob.status == AuditStatus.running),
        scans_queued=await _count(db, Scan, Scan.status == ScanStatus.queued)
        + await _count(db, AuditJob, started, AuditJob.status == AuditStatus.queued),
        scans_failed_today=await _count(db, Scan, Scan.status == ScanStatus.failed, Scan.created_at >= today)
        + await _count(db, AuditJob, AuditJob.status == AuditStatus.failed, AuditJob.started_at >= today),
        open_vulnerabilities=open_vulns,
    )


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    project_counts = select(Project.owner_id, func.count().label("n")).group_by(Project.owner_id).subquery()
    scan_counts = select(Scan.created_by, func.count().label("n")).group_by(Scan.created_by).subquery()
    rows = await db.execute(
        select(User, func.coalesce(project_counts.c.n, 0), func.coalesce(scan_counts.c.n, 0), Organization.name)
        .outerjoin(project_counts, project_counts.c.owner_id == User.id)
        .outerjoin(scan_counts, scan_counts.c.created_by == User.id)
        .outerjoin(Organization, Organization.id == User.organization_id)
        .order_by(User.created_at.desc(), User.email)
    )
    return [
        AdminUserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            role=u.role,
            created_at=u.created_at,
            project_count=projects,
            scan_count=scans,
            organization_name=org_name,
            org_role=u.org_role if org_name else None,
        )
        for u, projects, scans, org_name in rows.all()
    ]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: str,
    body: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    # An admin cannot lock themselves out, so there is always at least one super admin.
    if user.id == admin.id and (body.role not in (None, ROLE_SUPER_ADMIN) or body.is_active is False):
        raise HTTPException(400, "You cannot remove your own admin access or deactivate yourself")

    if body.role is not None and body.role != user.role:
        await log_admin_action(db, admin, "user.role", user.email, f"{user.role} to {body.role}")
        user.role = body.role
    if body.is_active is not None and body.is_active != user.is_active:
        await log_admin_action(db, admin, "user.reactivate" if body.is_active else "user.deactivate", user.email)
        user.is_active = body.is_active
    await db.flush()

    return AdminUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        role=user.role,
        created_at=user.created_at,
        project_count=await _count(db, Project, Project.owner_id == user.id),
        scan_count=await _count(db, Scan, Scan.created_by == user.id),
    )


@router.post("/users/{user_id}/reset-link")
async def create_reset_link(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_super_admin)):
    """A single-use link for a user who is locked out. The admin passes it on; it is shown only once."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if not user.is_active:
        raise HTTPException(400, "This account is deactivated. Reactivate it before sending a reset link.")
    token, expires = await password_reset.create_reset(db, user)
    await log_admin_action(db, admin, "user.reset_link", user.email)
    return {"url": password_reset.reset_url(token), "expires_at": expires, "email": user.email}


@router.post("/users/{user_id}/reset-two-step")
async def reset_two_step(user_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_super_admin)):
    """Turn off two-step sign-in for a user who has lost their authenticator app."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.totp_secret_encrypted = user.totp_enabled_at = user.totp_last_counter = None
    await log_admin_action(db, admin, "user.reset_two_step", user.email)
    return {"email": user.email}


@router.get("/scans", response_model=list[AdminScanOut])
async def list_all_scans(limit: int = 20, db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 100))
    rows = await db.execute(
        select(Scan, User.email).join(User, User.id == Scan.created_by).order_by(Scan.created_at.desc()).limit(limit)
    )
    items = [
        AdminScanOut(id=s.id, url=s.url, status=_value(s.status), progress=s.progress, created_at=s.created_at, owner_email=email)
        for s, email in rows.all()
    ]
    audit_rows = await db.execute(
        select(AuditJob, User.email)
        .join(User, User.id == AuditJob.created_by)
        .where(AuditJob.started_at.is_not(None))
        .order_by(AuditJob.created_at.desc())
        .limit(limit)
    )
    items += [
        AdminScanOut(id=a.id, url=a.label, status=_value(a.status), progress=a.progress, created_at=a.created_at, owner_email=email)
        for a, email in audit_rows.all()
    ]
    return sorted(items, key=lambda i: str(i.created_at), reverse=True)[:limit]


# ---------------------------------------------------------------------------
# Organisations
# ---------------------------------------------------------------------------

async def _org_out(db: AsyncSession, org: Organization) -> AdminOrgOut:
    owner_email = (
        await db.execute(select(User.email).where(User.organization_id == org.id, User.org_role == "owner").limit(1))
    ).scalar()
    return AdminOrgOut(
        id=org.id,
        name=org.name,
        account_type=org.account_type,
        status=org.status,
        seat_limit=org.seat_limit,
        scan_limit=org.scan_limit,
        member_count=await member_count(db, org.id),
        scans_this_month=await scans_this_month(db, org.id),
        owner_email=owner_email,
        created_at=org.created_at,
        billing_provider=org.billing_provider,
        billing_status=org.billing_status,
        billing_seats=org.billing_seats,
    )


async def _org_detail(db: AsyncSession, org: Organization) -> AdminOrgDetail:
    members = by_seniority(list((await db.execute(select(User).where(User.organization_id == org.id))).scalars().all()))
    return AdminOrgDetail(
        **(await _org_out(db, org)).model_dump(),
        members=[
            AdminOrgMember(id=m.id, full_name=m.full_name, email=m.email, org_role=m.org_role, is_active=m.is_active)
            for m in members
        ],
        ai_own_key=bool(org.ai_key_encrypted),
        ai_provider=PROVIDERS.get(org.ai_provider, {}).get("name") if org.ai_key_encrypted else None,
        ai_model=org.ai_model if org.ai_key_encrypted else None,
        ai_monthly_cap_usd=org.ai_monthly_cap_usd,
        ai_platform_cap_usd=settings.AI_MONTHLY_CAP_USD,
        ai_spend_this_month=round(await asyncio.to_thread(platform.month_spend, org.id), 2),
    )


@router.get("/organizations", response_model=list[AdminOrgOut])
async def list_organizations(db: AsyncSession = Depends(get_db)):
    orgs = (await db.execute(select(Organization).order_by(Organization.created_at.desc(), Organization.name))).scalars().all()
    return [await _org_out(db, org) for org in orgs]


@router.get("/organizations/{org_id}", response_model=AdminOrgDetail)
async def get_organization(org_id: str, db: AsyncSession = Depends(get_db)):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organisation not found")
    return await _org_detail(db, org)


@router.patch("/organizations/{org_id}", response_model=AdminOrgDetail)
async def update_organization(
    org_id: str,
    body: AdminOrgUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    """Change an organisation's account type, limits or status. Every change is written to the audit log."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organisation not found")
    sent = body.model_fields_set
    members = await member_count(db, org.id)

    if "account_type" in sent and body.account_type and body.account_type != org.account_type:
        if body.account_type == "individual" and members > 1:
            raise HTTPException(400, f"This organisation has {members} members. Remove all but one before making it Individual.")
        await log_admin_action(db, admin, "org.account_type", org.name, f"{org.account_type} to {body.account_type}")
        org.account_type = body.account_type
        if "seat_limit" not in sent:
            org.seat_limit = DEFAULT_SEATS[body.account_type]

    for field in ("seat_limit", "scan_limit"):
        if field in sent:
            value = getattr(body, field)
            if value is not None and value < 1:
                raise HTTPException(422, "A limit must be 1 or more, or empty for no limit")
            if field == "seat_limit" and value is not None and value < members:
                raise HTTPException(400, f"This organisation already has {members} members")
            if value != getattr(org, field):
                await log_admin_action(db, admin, f"org.{field}", org.name, f"{getattr(org, field) or 'no limit'} to {value or 'no limit'}")
                setattr(org, field, value)

    if "ai_monthly_cap_usd" in sent and body.ai_monthly_cap_usd != org.ai_monthly_cap_usd:
        cap = body.ai_monthly_cap_usd
        if cap is not None and not 0 <= cap <= 1_000_000:
            raise HTTPException(422, "The AI allowance must be 0 or more whole dollars, or empty to use the platform's figure")
        say = lambda v: "the platform's figure" if v is None else ("no limit" if v == 0 else f"${v}")
        await log_admin_action(db, admin, "org.ai_allowance", org.name, f"{say(org.ai_monthly_cap_usd)} to {say(cap)}")
        org.ai_monthly_cap_usd = cap

    if "status" in sent and body.status and body.status != org.status:
        await log_admin_action(db, admin, "org.suspend" if body.status == "suspended" else "org.reactivate", org.name)
        org.status = body.status

    await db.flush()
    return await _org_detail(db, org)


@router.delete("/organizations/{org_id}/ai-key", response_model=AdminOrgDetail)
async def remove_ai_key(org_id: str, db: AsyncSession = Depends(get_db), admin: User = Depends(require_super_admin)):
    """Take away an organisation's own AI key, for example one that leaked. It goes back to the platform's key."""
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organisation not found")
    if org.ai_key_encrypted:
        org.ai_key_encrypted, org.ai_provider, org.ai_model, org.ai_base_url = None, "anthropic", None, None
        await log_admin_action(db, admin, "org.ai_key_removed", org.name)
        await db.flush()
    return await _org_detail(db, org)


@router.get("/audit-log", response_model=list[AuditLogOut])
async def audit_log(limit: int = 100, db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 500))
    rows = await db.execute(
        select(AdminAuditLog, User.email)
        .join(User, User.id == AdminAuditLog.actor_id)
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id)
        .limit(limit)
    )
    return [
        AuditLogOut(id=entry.id, actor_email=email, action=entry.action, target=entry.target, detail=entry.detail, created_at=entry.created_at)
        for entry, email in rows.all()
    ]


@router.get("/audit-log.csv")
async def audit_log_csv(db: AsyncSession = Depends(get_db)):
    """The whole audit log as a spreadsheet, newest first."""
    import csv
    import io

    from fastapi.responses import Response

    rows = await db.execute(
        select(AdminAuditLog, User.email).join(User, User.id == AdminAuditLog.actor_id).order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id)
    )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["When (UTC)", "Who", "Action", "Target", "Detail"])
    for entry, email in rows.all():
        # A leading quote stops a spreadsheet treating a value as a formula.
        writer.writerow([entry.created_at.isoformat() if entry.created_at else "", email, entry.action]
                        + [("'" + v) if v[:1] in "=+-@" else v for v in (entry.target, entry.detail)])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="wiseflow-audit-log.csv"'})
