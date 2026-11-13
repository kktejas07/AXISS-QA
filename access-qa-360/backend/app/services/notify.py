"""
Telling people a scan has finished: Slack, Microsoft Teams, email, and the
comment and status on a GitHub pull request.

Nothing here may break a scan: every channel is tried by itself and failures are swallowed.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.secrets import decrypt
from app.models.audit_job import AuditJob, AuditStatus
from app.models.integration import Integration
from app.models.user import User
from app.services import findings as F, github, history
from app.services.mailer import email_configured, send_email

log = logging.getLogger(__name__)

CHAT_HOSTS = {"slack": ("hooks.slack.com",), "teams": (".webhook.office.com", ".logic.azure.com", ".powerplatform.com")}
FAIL_ON = {"critical": ["critical"], "high": ["critical", "high"], "never": []}


def chat_url_ok(kind: str, url: str) -> bool:
    """Only the real Slack and Teams webhook hosts, over https, so the server cannot be pointed somewhere else."""
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(host == h or (h.startswith(".") and host.endswith(h)) for h in CHAT_HOSTS.get(kind, ()))


async def send_chat(kind: str, url: str, text: str) -> bool:
    if not chat_url_ok(kind, url):
        return False
    body = {"text": text} if kind == "slack" else {"@type": "MessageCard", "@context": "https://schema.org/extensions", "summary": "Wiseflow scan", "text": text.replace("\n", "\n\n")}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            return (await client.post(url, json=body)).status_code < 300
    except httpx.HTTPError:
        return False


def link(job: AuditJob) -> str:
    return f"{settings.APP_URL.rstrip('/')}/audits/{job.id}"


def summary(job: AuditJob, found: list[dict], diff: dict | None) -> str:
    """A few plain lines: what was scanned, how it went, and what changed since last time."""
    if job.status == AuditStatus.failed:
        return f"The Wiseflow scan of {job.label} could not be completed.\n{link(job)}"
    n = F.counts(found)
    lines = [f"Wiseflow finished scanning {job.label}.",
             f"{len(found)} findings: {n['critical']} critical, {n['high']} high, {n['medium']} medium, {n['low']} low."]
    if diff is not None:
        lines.append(f"Since the last scan: {len(diff['new'])} new, {len(diff['fixed'])} fixed.")
        lines += [f"  New: [{f['severity']}] {f['title']}" for f in diff["new"][:5]]
    lines.append(link(job))
    return "\n".join(lines)


def pr_comment(job: AuditJob, found: list[dict], diff: dict | None) -> str:
    if job.status == AuditStatus.failed:
        return f"### Wiseflow scan\nThe scan could not be completed. [Open the scan]({link(job)})"
    n = F.counts(found)
    shown = diff["new"] if diff is not None else found
    heading = "New in this pull request" if diff is not None else "Findings"
    lines = ["### Wiseflow scan", "",
             f"**{len(found)} findings** in this branch: {n['critical']} critical, {n['high']} high, {n['medium']} medium, {n['low']} low."]
    if diff is not None:
        lines.append(f"Compared with the main line: **{len(diff['new'])} new**, {len(diff['fixed'])} fixed.")
    if shown:
        lines += ["", f"**{heading}**", "", "| Severity | Finding | Where |", "| --- | --- | --- |"]
        lines += [f"| {f['severity'].capitalize()} | {f['title'].replace('|', '/')} | {(f['location'] or '').replace('|', '/')} |" for f in shown[:15]]
        if len(shown) > 15:
            lines.append(f"\n…and {len(shown) - 15} more.")
    lines += ["", f"[Open the full scan]({link(job)})"]
    return "\n".join(lines)


def pr_state(job: AuditJob, found: list[dict], diff: dict | None, fail_on: str) -> tuple[str, str]:
    """(GitHub status, one-line reason). Only findings this pull request adds can fail it, when there is something to compare with."""
    if job.status == AuditStatus.failed:
        return "error", "The scan could not be completed"
    judged = diff["new"] if diff is not None else found
    blocking = [f for f in judged if f["severity"] in FAIL_ON.get(fail_on, FAIL_ON["high"])]
    what = "new " if diff is not None else ""
    if blocking:
        return "failure", f"{len(blocking)} {what}finding{'s' if len(blocking) != 1 else ''} at {fail_on} severity or above"
    return "success", f"No {what}findings at {fail_on} severity or above" if fail_on != "never" else f"{len(judged)} {what}findings (reported only)"


async def scan_finished(job_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(AuditJob, job_id)
            if not job or not job.organization_id or job.status not in (AuditStatus.completed, AuditStatus.partial, AuditStatus.failed):
                return
            trigger = job.trigger or {}
            rows = (await db.execute(select(Integration).where(Integration.organization_id == job.organization_id))).scalars().all()
            connections = {r.kind: r for r in rows}
            found = F.all_findings(job)
            before = await history.previous(db, job)
            diff = F.compare(F.all_findings(before), found) if before else None
            creator = await db.get(User, job.created_by)
    except Exception:
        log.exception("could not prepare notifications for scan %s", job_id)
        return

    text = summary(job, found, diff)
    for kind in ("slack", "teams"):
        row = connections.get(kind)
        if row and (trigger or row.config.get("events") == "all"):
            try:
                await send_chat(kind, decrypt(row.secret_encrypted) or "", text)
            except Exception:
                log.exception("%s notification failed", kind)

    if trigger.get("kind") == "schedule" and creator and email_configured():
        try:
            await send_email(creator.email, f"Wiseflow: scheduled scan of {job.label}", text)
        except Exception:
            log.exception("scheduled scan email failed")

    if trigger.get("kind") == "pull_request" and connections.get("github"):
        row = connections["github"]
        token = decrypt(row.secret_encrypted)
        if token:
            try:
                state, reason = pr_state(job, found, diff, row.config.get("fail_on", "high"))
                await github.comment(token, trigger["repo"], trigger["number"], pr_comment(job, found, diff))
                await github.set_status(token, trigger["repo"], trigger["sha"], state, reason, link(job))
            except Exception:
                log.exception("could not report scan %s to the pull request", job_id)
