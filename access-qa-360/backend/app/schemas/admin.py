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
