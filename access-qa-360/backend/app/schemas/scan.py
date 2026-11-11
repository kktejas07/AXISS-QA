from pydantic import BaseModel
from datetime import datetime


class ScanCreate(BaseModel):
    project_id: str | None = None
    url: str
    scan_type: str = "passive"
    auth_config: dict | None = None
    scope_include: str | None = None
    scope_exclude: str | None = None
    crawl_depth: int = 3
    rate_limit: int = 10
    scan_profile: str = "owasp_top10"
    # Accept frontend-style field names as aliases
    profile: str | None = None
    include_paths: list[str] | None = None
    exclude_paths: list[str] | None = None
    auth: dict | None = None

    def model_post_init(self, __context) -> None:
        # Remap frontend field names → backend field names
        if self.profile is not None and self.scan_profile == "owasp_top10":
            self.scan_profile = self.profile
        if self.include_paths is not None and self.scope_include is None:
            self.scope_include = ",".join(self.include_paths) if self.include_paths else None
        if self.exclude_paths is not None and self.scope_exclude is None:
            self.scope_exclude = ",".join(self.exclude_paths) if self.exclude_paths else None
        if self.auth is not None and self.auth_config is None:
            self.auth_config = self.auth

    def model_dump(self, **kwargs):
        """Return only the fields the Scan model understands."""
        d = super().model_dump(**kwargs)
        for extra in ("profile", "include_paths", "exclude_paths", "auth"):
            d.pop(extra, None)
        return d


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
