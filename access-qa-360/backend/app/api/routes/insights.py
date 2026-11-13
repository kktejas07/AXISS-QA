"""What changed between scans, how a target is trending, and where findings fall in the OWASP Top 10."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.database import get_db
from app.models.audit_job import AuditJob
from app.services import compliance, findings as F, history

router = APIRouter(prefix="/audits", tags=["insights"])


async def _job(db: AsyncSession, ctx: OrgContext, audit_id: str) -> AuditJob:
    job = (await db.execute(select(AuditJob).where(
        AuditJob.id == audit_id,
        or_(AuditJob.organization_id == ctx.org.id, and_(AuditJob.organization_id.is_(None), AuditJob.created_by == ctx.user.id)),
    ))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Scan not found")
    return job


def _brief(job: AuditJob) -> dict:
    found = F.all_findings(job)
    return {"id": job.id, "label": job.label, "created_at": job.created_at, "risk_score": job.risk_score,
            "findings": len(found), "counts": F.counts(found), "branch": job.repo_ref}


@router.get("/{audit_id}/changes")
async def changes(audit_id: str, against: str | None = None, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """New and fixed findings compared with an earlier scan of the same target (the one before, unless `against` names one)."""
    job = await _job(db, ctx, audit_id)
    series = await history.series(db, job)
    before = await _job(db, ctx, against) if against else await history.previous(db, job)
    if before and before.target_key != job.target_key:
        raise HTTPException(422, "Those two scans are of different things, so they cannot be compared")
    out = {"scan": _brief(job), "baseline": None, "new": [], "fixed": [], "unchanged": 0, "history": [_brief(j) for j in series]}
    if before:
        diff = F.compare(F.all_findings(before), F.all_findings(job))
        out.update(baseline=_brief(before), **diff)
    return out


@router.get("/{audit_id}/standards")
async def standards(audit_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    return compliance.report(F.all_findings(await _job(db, ctx, audit_id)))


@router.get("/{audit_id}/standards.csv")
async def standards_csv(audit_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    job = await _job(db, ctx, audit_id)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["OWASP Top 10 (2021)", "Category", "Severity", "Finding", "Where", "CWE"])
    for f in F.all_findings(job):
        code = compliance.category(f)
        if f["source"] in ("accessibility", "performance"):
            continue
        writer.writerow([code or "", compliance.OWASP.get(code, "Not in the Top 10"), f["severity"], f["title"], f["location"], f["cwe_id"]])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="wiseflow-standards-{job.id[:8]}.csv"'})
