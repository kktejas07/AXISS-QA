from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AdminOverview(BaseModel):
    users_total: int
    users_active: int
    super_admins: int
    projects_total: int
    scans_total: int
    scans_today: int
    scans_running: int
    scans_queued: int
    scans_failed_today: int
    open_vulnerabilities: dict[str, int]


class AdminUserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    role: str
    created_at: datetime
    project_count: int = 0
    scan_count: int = 0
    organization_name: str | None = None
    org_role: str | None = None


class AdminUserUpdate(BaseModel):
    role: Literal["user", "super_admin"] | None = None
    is_active: bool | None = None


class AdminScanOut(BaseModel):
    id: str
    url: str
    status: str
    progress: int
    created_at: datetime
    owner_email: str


class AdminOrgOut(BaseModel):
    id: str
    name: str
    account_type: str
    status: str
    seat_limit: int | None
    scan_limit: int | None
    member_count: int
    scans_this_month: int
    owner_email: str | None
    created_at: datetime
    # Card subscription, if the organisation pays through a provider.
    billing_provider: str | None = None
    billing_status: str | None = None
    billing_seats: int | None = None


class AdminOrgMember(BaseModel):
    id: str
    full_name: str
    email: str
    org_role: str
    is_active: bool


class AdminOrgDetail(AdminOrgOut):
    members: list[AdminOrgMember]
    # AI: whether the organisation uses its own key (the key itself is never sent), and its allowance on the platform's key.
    ai_own_key: bool = False
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_monthly_cap_usd: int | None = None
    ai_platform_cap_usd: int = 0
    ai_spend_this_month: float = 0


class AdminOrgUpdate(BaseModel):
    """Send only the fields to change. A limit of null means "no limit"."""

    account_type: Literal["individual", "team", "enterprise"] | None = None
    seat_limit: int | None = None
    scan_limit: int | None = None
    status: Literal["active", "suspended"] | None = None
    # Whole US dollars a month on the platform's AI key. null means the platform-wide figure applies; 0 means no limit.
    ai_monthly_cap_usd: int | None = None


class AuditLogOut(BaseModel):
    id: str
    actor_email: str
    action: str
    target: str
    detail: str
    created_at: datetime
