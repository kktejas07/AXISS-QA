"""Organisation rules: who may do what, seat and scan limits, and the admin audit trail."""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_job import AuditJob
from app.models.organization import AdminAuditLog, Invite, Organization
from app.models.user import User

# The permission matrix. Everyone in an organisation can see its scans and results.
PERMISSIONS: dict[str, set[str]] = {
    "scan.run": {"owner", "admin", "member"},     # create, upload to and start scans
    "members.manage": {"owner", "admin"},          # invite, change roles, remove
    "org.edit": {"owner", "admin"},                # rename the organisation
}

ROLE_NAMES = {"owner": "Owner", "admin": "Admin", "member": "Member", "viewer": "Viewer"}

# Seats a new organisation of each type starts with. None means no limit.
# A super admin can change the limit per organisation.
DEFAULT_SEATS: dict[str, int | None] = {"individual": 1, "team": 10, "enterprise": None}


_ROLE_ORDER = {"owner": 0, "admin": 1, "member": 2, "viewer": 3}


def by_seniority(members: list[User]) -> list[User]:
    """Owner first, then admins, members and viewers, each group by name."""
    return sorted(members, key=lambda m: (_ROLE_ORDER.get(m.org_role, 9), m.full_name.lower(), m.email))


def permissions_for(role: str) -> list[str]:
    return sorted(action for action, roles in PERMISSIONS.items() if role in roles)


async def create_personal_org(db: AsyncSession, user: User) -> Organization:
    """Give a user their own one-person organisation, with them as owner."""
    org = Organization(name=f"{user.full_name}'s workspace", account_type="individual", seat_limit=DEFAULT_SEATS["individual"])
    db.add(org)
    await db.flush()
    user.organization_id = org.id
    user.org_role = "owner"
    await db.flush()
    return org


async def ensure_org(db: AsyncSession, user: User) -> Organization:
    """The user's organisation, creating a personal one for accounts that predate organisations."""
    if user.organization_id:
        org = await db.get(Organization, user.organization_id)
        if org:
            return org
    return await create_personal_org(db, user)


async def member_count(db: AsyncSession, org_id: str) -> int:
    return (await db.execute(select(func.count()).select_from(User).where(User.organization_id == org_id))).scalar() or 0


async def pending_invite_count(db: AsyncSession, org_id: str) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(Invite).where(Invite.organization_id == org_id, Invite.accepted_at.is_(None))
        )
    ).scalar() or 0


async def scans_this_month(db: AsyncSession, org_id: str) -> int:
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        await db.execute(
            select(func.count()).select_from(AuditJob).where(AuditJob.organization_id == org_id, AuditJob.started_at >= start)
        )
    ).scalar() or 0


async def log_admin_action(db: AsyncSession, actor: User, action: str, target: str, detail: str = "") -> None:
    db.add(AdminAuditLog(actor_id=actor.id, action=action, target=target, detail=detail))
