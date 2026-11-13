"""The findings inbox, the software bill of materials, notifications and the getting-started checklist."""
import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.database import get_db
from app.models.audit_job import AuditJob, AuditStatus
from app.models.automation import ScanSchedule
from app.models.integration import Integration
from app.models.triage import STATUSES, FindingState
from app.models.user import User
from app.models.wise import WiseDocument
from app.services import findings as F
from app.services.history import DONE

router = APIRouter(tags=["workspace"])
MAX_TARGETS = 40


async def _latest_scans(db: AsyncSession, org_id: str) -> list[AuditJob]:
    """The most recent finished scan of each website, repository or app."""
    rows = (await db.execute(select(AuditJob).where(AuditJob.organization_id == org_id, AuditJob.status.in_(DONE))
                             .order_by(AuditJob.created_at.desc()).limit(300))).scalars().all()
    latest: dict[str, AuditJob] = {}
    for job in rows:
        # A pull request's branch is not the state of the product, so it never stands for its repository here.
        if (job.trigger or {}).get("kind") != "pull_request":
            latest.setdefault(job.target_key, job)
    return list(latest.values())[:MAX_TARGETS]


async def _states(db: AsyncSession, org_id: str) -> dict[tuple[str, str], FindingState]:
    rows = (await db.execute(select(FindingState).where(FindingState.organization_id == org_id))).scalars().all()
    return {(r.target_key, r.fingerprint): r for r in rows}


@router.get("/findings")
async def inbox(status: str | None = None, severity: str | None = None, assignee: str | None = None,
                db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Every finding from the latest scan of each target, with what the team decided about it."""
    states = await _states(db, ctx.org.id)
    people = {u.id: u.full_name for u in (await db.execute(select(User).where(User.organization_id == ctx.org.id))).scalars().all()}
    items = []
    for job in await _latest_scans(db, ctx.org.id):
        for f in F.all_findings(job):
            state = states.get((job.target_key, f["fingerprint"]))
            items.append({
                "audit_id": job.id, "app": job.label, "source": f["source"], "index": f["index"], "severity": f["severity"], "title": f["title"],
                "location": f["location"], "status": state.status if state else "open", "note": state.note if state else None,
                "assignee_id": state.assignee_id if state else None, "assignee": people.get(state.assignee_id) if state and state.assignee_id else None,
                "found_at": job.created_at,
            })
    counts = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    if status:
        items = [i for i in items if i["status"] == status]
    if severity:
        items = [i for i in items if i["severity"] == severity]
    if assignee:
        items = [i for i in items if (i["assignee_id"] or "none") == ("none" if assignee == "none" else (ctx.user.id if assignee == "me" else assignee))]
    items.sort(key=lambda i: (F.SEVERITIES.index(i["severity"]), i["app"]))
    return {"counts": counts, "total": sum(counts.values()), "items": items[:500]}


class StateIn(BaseModel):
    audit_id: str
    source: Literal["security", "mobile", "accessibility", "performance"]
    index: int = Field(ge=0)
    status: Literal["open", "fixed", "accepted", "false_positive"]
    assignee_id: str | None = None
    note: str | None = Field(default=None, max_length=500)


@router.put("/findings/state")
async def set_state(body: StateIn, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Record what the team decided about one finding. The decision follows the finding to later scans of the same target."""
    ctx.require("scan.run")
    job = (await db.execute(select(AuditJob).where(AuditJob.id == body.audit_id, AuditJob.organization_id == ctx.org.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Scan not found")
    finding = next((f for f in F.all_findings(job) if f["source"] == body.source and f["index"] == body.index), None)
    if not finding:
        raise HTTPException(404, "That finding is not part of this scan")
    if body.status in ("accepted", "false_positive") and not (body.note or "").strip():
        raise HTTPException(422, "Say why, so the next person understands the decision")
    if body.assignee_id:
        member = (await db.execute(select(User).where(User.id == body.assignee_id, User.organization_id == ctx.org.id))).scalar_one_or_none()
        if not member:
            raise HTTPException(422, "That person is not in your organisation")
    row = (await db.execute(select(FindingState).where(FindingState.organization_id == ctx.org.id, FindingState.target_key == job.target_key,
                                                       FindingState.fingerprint == finding["fingerprint"]))).scalar_one_or_none()
    if not row:
        row = FindingState(organization_id=ctx.org.id, target_key=job.target_key[:600], fingerprint=finding["fingerprint"], updated_by=ctx.user.id)
        db.add(row)
    row.status, row.assignee_id, row.note, row.updated_by = body.status, body.assignee_id, (body.note or "").strip() or None, ctx.user.id
    await db.flush()
    return {"status": row.status, "assignee_id": row.assignee_id, "note": row.note}


@router.get("/audits/{audit_id}/sbom.json")
async def sbom(audit_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """The packages a code scan found, as a CycloneDX software bill of materials."""
    job = (await db.execute(select(AuditJob).where(AuditJob.id == audit_id, AuditJob.organization_id == ctx.org.id))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Scan not found")
    packages = (job.tier1_result or {}).get("packages")
    if not packages:
        raise HTTPException(404, "This scan has no package list. Scan the code again to get one.")
    purl_type = {"PyPI": "pypi", "npm": "npm", "Maven": "maven", "Go": "golang", "Packagist": "composer", "RubyGems": "gem", "crates.io": "cargo", "NuGet": "nuget"}
    components = [{
        "type": "library", "name": p["name"], "version": p["version"],
        "purl": f"pkg:{purl_type.get(p['ecosystem'], p['ecosystem'].lower())}/{p['name']}@{p['version']}",
        "properties": [{"name": "wiseflow:manifest", "value": p["manifest"]}],
    } for p in packages]
    doc = {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
           "metadata": {"timestamp": (job.completed_at or job.created_at).isoformat(), "component": {"type": "application", "name": job.label},
                        "tools": [{"vendor": "Wiseflow", "name": "Wiseflow code scan"}]},
           "components": components}
    return Response(json.dumps(doc, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="wiseflow-sbom-{job.id[:8]}.cdx.json"'})


@router.get("/notifications")
async def notifications(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """What happened lately: scans that finished and scheduled runs that were skipped. Newest first."""
    since = datetime.now(timezone.utc) - timedelta(days=14)
    items = []
    jobs = (await db.execute(select(AuditJob).where(AuditJob.organization_id == ctx.org.id, AuditJob.completed_at.is_not(None), AuditJob.completed_at >= since)
                             .order_by(AuditJob.completed_at.desc()).limit(15))).scalars().all()
    for job in jobs:
        failed = job.status == AuditStatus.failed
        how = {"schedule": "Scheduled scan", "pull_request": "Pull request scan"}.get((job.trigger or {}).get("kind"), "Scan")
        text = f"{how} of {job.label} could not be completed" if failed else f"{how} of {job.label} finished: {job.critical_count} critical, {job.high_count} high"
        items.append({"id": f"scan-{job.id}", "at": job.completed_at, "text": text, "path": f"/audits/{job.id}", "tone": "bad" if failed or job.critical_count else "ok"})
    skipped = (await db.execute(select(ScanSchedule).where(ScanSchedule.organization_id == ctx.org.id, ScanSchedule.last_note.is_not(None), ScanSchedule.last_run_at >= since))).scalars().all()
    for s in skipped:
        items.append({"id": f"schedule-{s.id}-{s.last_run_at.isoformat()}", "at": s.last_run_at, "text": f"The scheduled scan of {s.target} did not run. {s.last_note}", "path": "/schedules", "tone": "bad"})
    stamp = lambda i: i["at"].replace(tzinfo=timezone.utc) if i["at"].tzinfo is None else i["at"]
    return sorted(items, key=stamp, reverse=True)[:20]


@router.get("/onboarding")
async def onboarding(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """First steps for a new organisation, and which are already done."""
    org = ctx.org.id
    count = lambda model, *where: db.execute(select(func.count()).select_from(model).where(*where))
    scans = (await count(AuditJob, AuditJob.organization_id == org, AuditJob.started_at.is_not(None))).scalar_one()
    schedules = (await count(ScanSchedule, ScanSchedule.organization_id == org)).scalar_one()
    connections = (await count(Integration, Integration.organization_id == org)).scalar_one()
    documents = (await count(WiseDocument, WiseDocument.organization_id == org)).scalar_one()
    steps = [
        {"id": "scan", "label": "Run your first scan", "about": "Paste a web address, upload a build or link a repository.", "path": "/scans/new", "done": scans > 0},
        {"id": "schedule", "label": "Put a scan on a timetable", "about": "Re-scan every day, week or month and hear what changed.", "path": "/schedules", "done": schedules > 0},
        {"id": "connect", "label": "Connect where your team works", "about": "Slack, Teams, Jira, GitHub, Linear or Azure Boards.", "path": "/settings", "done": connections > 0},
        {"id": "document", "label": "Give Wise a document", "about": "Requirements or user stories, so answers are about your product.", "path": "/settings#wise", "done": documents > 0},
        {"id": "two-step", "label": "Turn on two-step sign-in", "about": "A code from your phone as well as your password.", "path": "/settings", "done": bool(ctx.user.totp_enabled_at)},
    ]
    return {"steps": steps, "done": sum(1 for s in steps if s["done"]), "total": len(steps)}
