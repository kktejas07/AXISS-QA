from pydantic import BaseModel
from datetime import datetime


class ScanCreate(BaseModel):
    project_id: str
    url: str
    scan_type: str = "passive"
    auth_config: dict | None = None
    scope_include: str | None = None
    scope_exclude: str | None = None
    crawl_depth: int = 3
    rate_limit: int = 10
    scan_profile: str = "owasp_top10"


class ScanOut(BaseModel):
    id: str
    project_id: str
    url: str
    scan_type: str
    status: str
    scan_profile: str
    progress: int
    crawl_depth: int
    rate_limit: int
    scope_include: str | None
    scope_exclude: str | None
    auth_config: dict | None
    created_by: str
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ScanProgress(BaseModel):
    id: str
    status: str
    progress: int

    model_config = {"from_attributes": True}


class ScanSummary(ScanOut):
    vulnerability_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    gap_count: int = 0
    test_case_count: int = 0
