"""Super admin console: platform-wide numbers and user management.

Every route here requires the super_admin role (see require_super_admin).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.database import get_db
from app.models.audit_job import AuditJob, AuditStatus
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.user import ROLE_SUPER_ADMIN, User
from app.models.vulnerability import Severity, VulnStatus, Vulnerability
from app.schemas.admin import AdminOverview, AdminScanOut, AdminUserOut, AdminUserUpdate

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
        select(User, func.coalesce(project_counts.c.n, 0), func.coalesce(scan_counts.c.n, 0))
        .outerjoin(project_counts, project_counts.c.owner_id == User.id)
        .outerjoin(scan_counts, scan_counts.c.created_by == User.id)
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
        )
        for u, projects, scans in rows.all()
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

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
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
