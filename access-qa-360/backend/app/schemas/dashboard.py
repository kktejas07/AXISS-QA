from datetime import datetime

from pydantic import BaseModel


class RecentScan(BaseModel):
    id: str
    # "audit" is a scan from the main flow (/audits/{id}); "scan" is a quick security scan (/scans/{id}).
    kind: str = "scan"
    url: str
    status: str
    progress: int
    created_at: datetime
    critical: int = 0
    high: int = 0
    total: int = 0


class TopFinding(BaseModel):
    id: str
    scan_id: str
    severity: str
    title: str
    affected_url: str
    kind: str = "scan"


class DashboardSummary(BaseModel):
    projects: int
    scans: int
    open_vulnerabilities: dict[str, int]
    qa_gaps: int
    test_cases: dict[str, int]
    recent_scans: list[RecentScan]
    top_findings: list[TopFinding]
