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


@router.get("/{audit_id}/flows")
async def flows(audit_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """The crawled pages as a map: each page is a node, each link between two crawled pages an arrow."""
    job = await _job(db, ctx, audit_id)
    pages = [p for p in (job.tier1_result or {}).get("pages") or [] if not p.get("error")]
    by_url = {p["url"].rstrip("/"): i for i, p in enumerate(pages)}
    edges, seen = [], set()
    for i, p in enumerate(pages):
        for link in p.get("links") or []:
            j = by_url.get(str(link).rstrip("/"))
            if j is not None and j != i and (i, j) not in seen:
                seen.add((i, j))
                edges.append({"from": i, "to": j})
    # How many clicks each page is from the start page, for laying the map out in columns.
    depth = {0: 0} if pages else {}
    queue = [0] if pages else []
    while queue:
        at = queue.pop(0)
        for e in edges:
            if e["from"] == at and e["to"] not in depth:
                depth[e["to"]] = depth[at] + 1
                queue.append(e["to"])
    nodes = [{
        "id": i, "path": p.get("path") or "/", "url": p["url"], "title": (p.get("title") or "")[:120], "status": p.get("status_code"),
        "depth": depth.get(i, max(depth.values(), default=0) + 1), "forms": len(p.get("forms") or []),
        "form_fields": [f.get("name") or f.get("type") or "field" for form in (p.get("forms") or [])[:3] for f in (form.get("fields") or form.get("inputs") or [])[:8]],
        "api_calls": [f"{c.get('method', 'GET')} {c.get('url', '')}"[:160] for c in (p.get("api_calls") or [])[:8]],
        "a11y": len(p.get("a11y_violations") or []), "lcp_ms": (p.get("performance") or {}).get("lcp_ms"),
    } for i, p in enumerate(pages)]
    return {"nodes": nodes, "edges": edges, "pages_crawled": (job.tier1_result or {}).get("pages_audited", len(pages)), "shown": len(nodes)}


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
