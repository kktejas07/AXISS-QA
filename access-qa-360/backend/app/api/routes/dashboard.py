"""The signed-in user's own overview: only data from scans they created."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.audit_job import AuditJob
from app.models.project import Project
from app.models.qa_gap import QAGap
from app.models.scan import Scan
from app.models.test_case import TestCase
from app.models.user import User
from app.models.vulnerability import Severity, VulnStatus, Vulnerability
from app.schemas.dashboard import DashboardSummary, RecentScan, TopFinding

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

OPEN_STATUSES = [VulnStatus.open, VulnStatus.confirmed]
SEVERITY_ORDER = {s.value: i for i, s in enumerate(Severity)}


def _value(enum_or_str) -> str:
    return getattr(enum_or_str, "value", enum_or_str)


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    mine = Scan.created_by == user.id

    projects = (await db.execute(select(func.count()).select_from(Project).where(Project.owner_id == user.id))).scalar() or 0
    scans = (await db.execute(select(func.count()).select_from(Scan).where(mine))).scalar() or 0

    open_vulns = {s.value: 0 for s in Severity}
    rows = await db.execute(
        select(Vulnerability.severity, func.count())
        .join(Scan, Scan.id == Vulnerability.scan_id)
        .where(mine, Vulnerability.status.in_(OPEN_STATUSES))
        .group_by(Vulnerability.severity)
    )
    for severity, count in rows.all():
        open_vulns[_value(severity)] = count

    qa_gaps = (
        await db.execute(select(func.count()).select_from(QAGap).join(Scan, Scan.id == QAGap.scan_id).where(mine))
    ).scalar() or 0

    test_cases: dict[str, int] = {}
    rows = await db.execute(
        select(TestCase.test_type, func.count())
        .join(Scan, Scan.id == TestCase.scan_id)
        .where(mine)
        .group_by(TestCase.test_type)
    )
    for test_type, count in rows.all():
        test_cases[_value(test_type)] = count

    recent = (await db.execute(select(Scan).where(mine).order_by(Scan.created_at.desc()).limit(5))).scalars().all()
    per_scan: dict[str, dict[str, int]] = {s.id: {} for s in recent}
    if recent:
        rows = await db.execute(
            select(Vulnerability.scan_id, Vulnerability.severity, func.count())
            .where(Vulnerability.scan_id.in_(list(per_scan)), Vulnerability.status.in_(OPEN_STATUSES))
            .group_by(Vulnerability.scan_id, Vulnerability.severity)
        )
        for scan_id, severity, count in rows.all():
            per_scan[scan_id][_value(severity)] = count
    recent_scans = [
        RecentScan(
            id=s.id,
            url=s.url,
            status=_value(s.status),
            progress=s.progress,
            created_at=s.created_at,
            critical=per_scan[s.id].get("critical", 0),
            high=per_scan[s.id].get("high", 0),
            total=sum(per_scan[s.id].values()),
        )
        for s in recent
    ]

    rows = await db.execute(
        select(Vulnerability)
        .join(Scan, Scan.id == Vulnerability.scan_id)
        .where(
            mine,
            Vulnerability.status.in_(OPEN_STATUSES),
            Vulnerability.severity.in_([Severity.critical, Severity.high]),
        )
        .order_by(Vulnerability.created_at.desc())
        .limit(50)
    )
    worst_first = sorted(rows.scalars().all(), key=lambda v: SEVERITY_ORDER[_value(v.severity)])
    top_findings = [
        TopFinding(id=v.id, scan_id=v.scan_id, severity=_value(v.severity), title=v.title, affected_url=v.affected_url)
        for v in worst_first[:5]
    ]

    # ---- scans from the main flow (audit jobs). Drafts that never started are left out.
    my_audits = (AuditJob.created_by == user.id, AuditJob.started_at.is_not(None))
    audit_count, audit_critical, audit_high, audit_tests = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(AuditJob.critical_count), 0),
                func.coalesce(func.sum(AuditJob.high_count), 0),
                func.coalesce(func.sum(AuditJob.total_test_cases), 0),
            ).where(*my_audits)
        )
    ).one()
    scans += audit_count
    open_vulns["critical"] += int(audit_critical)
    open_vulns["high"] += int(audit_high)
    if audit_tests:
        test_cases["manual"] = test_cases.get("manual", 0) + int(audit_tests)

    audits = (await db.execute(select(AuditJob).where(*my_audits).order_by(AuditJob.created_at.desc()).limit(5))).scalars().all()
    for a in audits:
        found = list((a.tier3_result or {}).get("findings", [])) + [
            {**flag, "affected_url": a.label} for flag in (a.tier2_result or {}).get("security_flags", [])
        ]
        recent_scans.append(
            RecentScan(
                id=a.id, kind="audit", url=a.label, status=_value(a.status), progress=a.progress,
                created_at=a.created_at, critical=a.critical_count, high=a.high_count, total=len(found),
            )
        )
        for i, item in enumerate(found):
            severity = str(item.get("severity", "")).lower()
            if severity in ("critical", "high"):
                top_findings.append(
                    TopFinding(
                        id=f"{a.id}:{item.get('id', i)}", scan_id=a.id, kind="audit", severity=severity,
                        title=item.get("title", "Finding"), affected_url=item.get("affected_url") or a.label,
                    )
                )
    recent_scans = sorted(recent_scans, key=lambda r: str(r.created_at), reverse=True)[:6]
    top_findings = sorted(top_findings, key=lambda t: SEVERITY_ORDER[t.severity])[:5]

    return DashboardSummary(
        projects=projects,
        scans=scans,
        open_vulnerabilities=open_vulns,
        qa_gaps=qa_gaps,
        test_cases=test_cases,
        recent_scans=recent_scans,
        top_findings=top_findings,
    )
