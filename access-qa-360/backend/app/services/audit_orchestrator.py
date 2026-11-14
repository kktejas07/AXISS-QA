"""
Audit Orchestrator — ties all 5 tiers together under one AuditJob.

Tier 1  Web QA (Playwright): crawl + test generation + accessibility
Tier 2  Mobile QA (Appium): APK/IPA/store URL + test generation
Tier 3  API / Cyber security: BOLA, JWT, CORS, rate limit, secrets, subdomains
Tier 4  Manual QA checklists (Claude): per-route checklist generation
Tier 5  Unified report + executive summary (Claude Sonnet)
"""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select, update as sa_update

from app.core.database import AsyncSessionLocal
from app.models.audit_job import AuditJob, AuditStatus
from app.services.web_auditor import (
    crawl_and_audit, generate_playwright_tests, generate_manual_test_cases, summarise_a11y, summarise_performance
)
from app.services.mobile_auditor import run_mobile_audit
from app.services.api_auditor import run_api_audit
from app.services import api_spec_auditor, chatbot_auditor, code_auditor, web_checks
from app.core.secrets import decrypt

from app.core.ai import ai_client, ai_context, org_context
from app.core import netguard
from app.core.config import settings
from app.core.storage import storage_path

ai = ai_client("Scan summary")

# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------

async def _set_progress(job_id: str, progress: int, **kwargs):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
        job = res.scalar_one_or_none()
        if job:
            job.progress = progress
            for k, v in kwargs.items():
                setattr(job, k, v)
            await db.commit()


async def _set_progress_only(job_id: str, **kwargs):
    """Update fields without touching progress."""
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(AuditJob).where(AuditJob.id == job_id))).scalar_one_or_none()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            await db.commit()


# ---------------------------------------------------------------------------
# Tier 5 — Unified report + executive summary
# ---------------------------------------------------------------------------

UNIFIED_SUMMARY_PROMPT = """You are a senior security and QA consultant. Write a concise executive summary (3–4 paragraphs, max 300 words) for a full application audit.

Application: {app_name}
Target URL: {url}
Audit date: {date}

Web QA Results:
  Pages crawled: {pages_crawled}
  Accessibility violations: {a11y_total} ({a11y_critical} critical, {a11y_serious} serious)
  Playwright tests generated: {playwright_test_count}

Mobile Audit: {mobile_summary}

API/Cyber Security:
  Total findings: {cyber_total}
  Critical: {cyber_critical}, High: {cyber_high}, Medium: {cyber_medium}
  JS secrets found: {secrets_count}
  Subdomains enumerated: {subdomain_count}

Manual QA Test Cases Generated: {manual_total}

Top Issues:
{top_issues}

Write in business English. Paragraph 1: overall posture.
Paragraph 2: top 3 risks and business impact.
Paragraph 3: QA coverage assessment.
Paragraph 4: immediate recommended actions.
Return ONLY the paragraphs, no headers or bullets."""


CODE_SUMMARY_PROMPT = """You are a senior security and QA consultant. Write a concise executive summary (3 paragraphs, max 250 words) of a static review of an application's source code. Nothing was run; the code was only read.

Application: {app_name}
Audit date: {date}
Files read: {files} ({languages})
HTTP routes found: {routes}

Security findings: {total} ({critical} critical, {high} high, {medium} medium)
  Leaked secrets: {secrets}
  Risky code patterns: {code}
  Vulnerable dependencies: {deps} ({dep_note})

Test coverage by file name and reference (not measured by running tests):
  Source files: {source_files}, test files: {test_files}
  Source files no test refers to: {untested_files}
  Routes no test refers to: {untested_routes} of {routes}

Top issues:
{top_issues}

Write in business English. Paragraph 1: overall posture. Paragraph 2: the top risks and their business impact.
Paragraph 3: where tests are missing and what to do first.
Return ONLY the paragraphs, no headers or bullets."""


async def _generate_code_summary(job: AuditJob) -> str:
    t1, t3 = job.tier1_result or {}, job.tier3_result or {}
    findings = t3.get("findings", [])
    gaps = t1.get("qa_gaps", {})
    deps = t3.get("dependencies", {})
    by_check = lambda name: sum(1 for f in findings if f.get("check") == name)
    prompt = CODE_SUMMARY_PROMPT.format(
        app_name=job.label,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        files=t1.get("files_scanned", 0),
        languages=", ".join(t1.get("languages", {})) or "unknown",
        routes=len(t1.get("routes", [])),
        total=len(findings),
        critical=_count(findings, "critical"), high=_count(findings, "high"), medium=_count(findings, "medium"),
        secrets=by_check("secrets"), code=by_check("code") + by_check("config"), deps=by_check("dependency"),
        dep_note=deps.get("reason") or f"{deps.get('packages_checked', 0)} packages checked",
        source_files=gaps.get("source_files", 0), test_files=gaps.get("test_files", 0),
        untested_files=gaps.get("untested_file_count", 0), untested_routes=gaps.get("untested_route_count", 0),
        top_issues="\n".join(f"- [{f.get('severity', '?').upper()}] {f.get('title', '?')} ({f.get('affected_url', '')})" for f in findings[:6]) or "No findings.",
    )
    msg = await ai.messages.create(model="claude-sonnet-4-5", max_tokens=700, messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text.strip()


async def _generate_unified_summary(job: AuditJob) -> str:
    if job.is_code:
        return await _generate_code_summary(job)
    t1 = job.tier1_result or {}
    t2 = job.tier2_result or {}
    t3 = job.tier3_result or {}
    t4 = job.tier4_result or {}

    # Web stats
    pages = t1.get("pages_audited", 0)
    a11y = t1.get("a11y_summary", {})
    pw_test_count = (t1.get("playwright_tests") or "").count("def test_")

    # Mobile
    mobile_summary = "Not applicable" if not t2 else (
        f"{t2.get('platform', 'unknown')} app '{t2.get('app_name', '')}'; "
        f"{len(t2.get('security_flags', []))} security flags; "
        f"{len(t2.get('manual_test_cases', []))} mobile test cases"
    )

    # Cyber
    findings = t3.get("findings", [])
    cyber_total = len(findings)
    cyber_critical = sum(1 for f in findings if f.get("severity") == "critical")
    cyber_high = sum(1 for f in findings if f.get("severity") == "high")
    cyber_medium = sum(1 for f in findings if f.get("severity") == "medium")
    secrets_count = len(t3.get("js_secrets", []))
    subdomain_count = len(t3.get("subdomains_found", []))

    # Manual QA
    manual_total = len(t4.get("test_cases", []))

    # Top issues
    all_findings = findings + [
        {"severity": f.get("severity",""), "title": f.get("title","")}
        for f in t1.get("a11y_summary", {}).get("violations", [])[:3]
    ]
    top_issues = "\n".join(
        f"- [{f.get('severity','?').upper()}] {f.get('title','?')}"
        for f in sorted(all_findings, key=lambda x: ["critical","high","medium","low",""].index(x.get("severity","")) if x.get("severity","") in ["critical","high","medium","low",""] else 99)[:5]
    ) or "No critical findings."

    prompt = UNIFIED_SUMMARY_PROMPT.format(
        app_name=job.label,
        url=job.target_url or "not provided (mobile build)",
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        pages_crawled=pages,
        a11y_total=a11y.get("total_violations", 0),
        a11y_critical=a11y.get("critical", 0),
        a11y_serious=a11y.get("serious", 0),
        playwright_test_count=pw_test_count,
        mobile_summary=mobile_summary,
        cyber_total=cyber_total,
        cyber_critical=cyber_critical,
        cyber_high=cyber_high,
        cyber_medium=cyber_medium,
        secrets_count=secrets_count,
        subdomain_count=subdomain_count,
        manual_total=manual_total,
        top_issues=top_issues,
    )

    msg = await ai.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


async def _write_unified_pdf(job: AuditJob, summary: str) -> str:
    """Write a unified PDF report. Returns file path."""
    path = storage_path("reports", f"audit_{job.id}.pdf")

    t1 = job.tier1_result or {}
    t2 = job.tier2_result or {}
    t3 = job.tier3_result or {}

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib import colors
        from xml.sax.saxutils import escape

        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        # Cover
        story.append(Paragraph("Application Audit Report", styles["Title"]))
        story.append(Paragraph(f"App: {job.label}", styles["Normal"]))
        if job.target_url:
            story.append(Paragraph(f"Address: {job.target_url}", styles["Normal"]))
        story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
        story.append(Spacer(1, 0.5*cm))

        # Executive Summary
        story.append(Paragraph("Executive Summary", styles["Heading1"]))
        for para in summary.split("\n\n"):
            story.append(Paragraph(para.strip(), styles["Normal"]))
            story.append(Spacer(1, 0.3*cm))

        # Risk Score
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(f"Overall Risk Score: {job.risk_score or '—'}/100", styles["Heading2"]))
        story.append(Paragraph(
            f"Critical: {job.critical_count} · High: {job.high_count} · "
            f"{'Files read' if job.is_code else 'Pages Audited'}: {job.total_pages_audited} · Test Cases: {job.total_test_cases}",
            styles["Normal"]
        ))
        story.append(Spacer(1, 0.5*cm))

        # Cyber findings
        findings = t3.get("findings", [])
        if findings:
            story.append(Paragraph("Security Findings", styles["Heading1"]))
            for f in findings[:30]:
                sev = f.get("severity","?").upper()
                story.append(Paragraph(f"[{sev}] {f.get('title','?')}", styles["Heading3"]))
                if job.is_code and f.get("affected_url"):
                    story.append(Paragraph(f"<b>Where:</b> {escape(str(f['affected_url']))}", styles["Normal"]))
                story.append(Paragraph(escape(f.get("description","")[:600]), styles["Normal"]))
                if f.get("remediation"):
                    story.append(Paragraph(f"<b>Remediation:</b> {escape(str(f['remediation']))}", styles["Normal"]))
                story.append(Spacer(1, 0.3*cm))

        # Mobile build checks
        flags = t2.get("security_flags", [])
        if flags:
            story.append(Paragraph("Mobile Build Findings", styles["Heading1"]))
            for fl in flags[:30]:
                story.append(Paragraph(f"[{str(fl.get('severity','?')).upper()}] {fl.get('title','?')}", styles["Heading3"]))
                story.append(Paragraph(str(fl.get("detail", ""))[:400], styles["Normal"]))
                story.append(Spacer(1, 0.3*cm))

        # Source code scans: where tests are missing
        gaps = t1.get("qa_gaps") or {}
        if gaps:
            story.append(Paragraph("Where tests are missing", styles["Heading1"]))
            story.append(Paragraph(
                f"{gaps.get('source_files', 0)} source files and {gaps.get('test_files', 0)} test files were read. "
                f"{gaps.get('untested_file_count', 0)} source files and {gaps.get('untested_route_count', 0)} of "
                f"{gaps.get('route_count', 0)} routes are not referred to by any test. This compares names and text; "
                "the tests were not run.", styles["Normal"]))
            story.append(Spacer(1, 0.3*cm))
            for r in gaps.get("untested_routes", [])[:25]:
                story.append(Paragraph(escape(f"{r.get('method', '')} {r.get('path', '')}  ({r.get('file', '')})"), styles["Normal"]))
            if gaps.get("untested_files"):
                story.append(Spacer(1, 0.3*cm))
                story.append(Paragraph("Largest files without tests", styles["Heading3"]))
                for u in gaps["untested_files"][:25]:
                    story.append(Paragraph(escape(f"{u.get('path', '')}  ({u.get('lines', 0)} lines)"), styles["Normal"]))
            story.append(Spacer(1, 0.3*cm))

        # Accessibility
        a11y = t1.get("a11y_summary", {})
        if a11y.get("violations"):
            story.append(Paragraph("Accessibility Findings (WCAG 2.1 AA)", styles["Heading1"]))
            for v in a11y["violations"][:20]:
                story.append(Paragraph(
                    f"[{v.get('impact','?').upper()}] {v.get('id','?')} — {v.get('description','')[:200]}",
                    styles["Normal"]
                ))
                story.append(Spacer(1, 0.2*cm))

        doc.build(story)
    except ImportError:
        # Fallback plain text
        lines = [
            "APPLICATION AUDIT REPORT",
            f"App: {job.label}",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "EXECUTIVE SUMMARY",
            summary,
            "",
            "FINDINGS (JSON)",
            json.dumps(t3.get("findings", []), indent=2, default=str),
        ]
        with open(path, "w") as f:
            f.write("\n".join(lines))

    return path


# ---------------------------------------------------------------------------
# Main audit runner
# ---------------------------------------------------------------------------

DEPTH_LIMITS = {"quick": (1, 10), "standard": (3, 40), "deep": (4, 80)}  # (crawl depth, max pages)
ALL_OUTPUTS = ["security", "manual", "playwright", "appium"]


def _reason(e: Exception) -> str:
    """First line of an error, short enough to show a user."""
    lines = str(e).strip().splitlines()
    return (lines[0] if lines else type(e).__name__)[:300]


def _fallback_summary(job: AuditJob, findings: int) -> str:
    """Plain summary used when the AI-written one cannot be produced."""
    return (
        f"This scan of {job.label} found {findings} security "
        f"{'finding' if findings == 1 else 'findings'}: {job.critical_count or 0} critical and "
        f"{job.high_count or 0} high. {'Files read' if job.is_code else 'Pages mapped'}: {job.total_pages_audited or 0}. "
        f"Manual test cases written: {job.total_test_cases or 0}.\n\n"
        "Fix the critical and high findings first; each one is listed in this report with its recommended fix."
    )


def _count(items: list[dict], severity: str) -> int:
    return sum(1 for i in items if str(i.get("severity", "")).lower() == severity)


async def run_audit(audit_job_id: str):
    """Run the scan, then tell whoever is waiting for it (chat, email, the pull request)."""
    try:
        await _run_audit(audit_job_id)
    finally:
        from app.services import notify

        # The sign-in details were only needed for the crawl. Do not keep them.
        async with AsyncSessionLocal() as db:
            await db.execute(sa_update(AuditJob).where(AuditJob.id == audit_job_id, AuditJob.login_encrypted.is_not(None)).values(login_encrypted=None))
            await db.commit()

        await notify.scan_finished(audit_job_id)


async def _run_audit(audit_job_id: str):
    """
    Run the tiers the user asked for and update the AuditJob throughout.

    job.outputs decides what is produced ("security", "manual", "playwright",
    "appium"); a tier with nothing to do is marked "skipped". Jobs created
    before outputs existed (outputs is None) run everything.
    """
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AuditJob).where(AuditJob.id == audit_job_id))
        job = res.scalar_one_or_none()
        if not job:
            return
        target_url = job.target_url
        mobile_url = job.mobile_url
        apk_path = job.apk_path
        ipa_path = job.ipa_path
        outputs = set(job.outputs or ALL_OUTPUTS)
        depth = job.depth or "standard"
        is_code = job.is_code
        is_api = job.source_type == "api"
        is_chatbot = job.source_type == "chatbot"
        login = None
        if job.login_encrypted:
            try:
                login = json.loads(decrypt(job.login_encrypted) or "null")
            except ValueError:
                login = None
        # AI calls made during this scan are counted against its organisation.
        ai_context.set(await org_context(db, job.organization_id, job.id))

    if is_code:
        await _run_code_audit(audit_job_id)
        return
    if is_api:
        await _run_api_spec_audit(audit_job_id)
        return
    if is_chatbot:
        await _run_chatbot_audit(audit_job_id, login)
        return

    max_depth, max_pages = DEPTH_LIMITS.get(depth, DEPTH_LIMITS["standard"])
    critical = high = 0
    tier_states: list[str] = []

    refused = await asyncio.to_thread(netguard.private_target, target_url)
    if refused:
        # Asked again here because a name can be pointed at a private address after the scan was created.
        await _set_progress(audit_job_id, 100, status=AuditStatus.failed, tier1_status="failed", tier1_result={"error": refused},
                            tier2_status="skipped", tier3_status="skipped", tier4_status="skipped", tier5_status="skipped", completed_at=datetime.now(timezone.utc))
        return

    await _set_progress(audit_job_id, 5, status=AuditStatus.running)

    # ---- Tier 1: map the web app, write Playwright tests and manual cases ----
    tier1_data: dict = {}
    if target_url:
        await _set_progress(audit_job_id, 8, tier1_status="running")
        crawl_report: dict = {}
        try:
            pages = await crawl_and_audit(
                target_url,
                max_depth=max_depth,
                max_pages=max_pages,
                capture_screenshots=True,
                run_a11y=True,
                login=login,
                report=crawl_report,
            )
            if not pages or all(p.error for p in pages):
                raise RuntimeError("Could not load any page at that address")
            playwright_tests = await generate_playwright_tests(pages, target_url) if "playwright" in outputs else ""
            manual_cases = await generate_manual_test_cases(pages) if "manual" in outputs else []
            tier1_data = {
                "pages_audited": len(pages),
                "pages": [p.to_dict() for p in pages[:20]],
                "a11y_summary": summarise_a11y(pages),
                "performance": summarise_performance(pages),
                # "ok", or why the sign-in did not work. Absent when the scan was not asked to sign in.
                **({"sign_in": crawl_report.get("login", "The sign-in was not attempted")} if login else {}),
                "playwright_tests": playwright_tests,
                "manual_test_cases": manual_cases,
                "routes_found": sorted({p.path for p in pages}),
            }
            tier_states.append("completed")
            await _set_progress(
                audit_job_id, 30,
                tier1_status="completed",
                tier1_result=tier1_data,
                total_pages_audited=len(pages),
                total_test_cases=len(manual_cases),
            )
        except Exception as e:
            tier1_data = {"error": _reason(e)}
            tier_states.append("failed")
            await _set_progress(audit_job_id, 30, tier1_status="failed", tier1_result=tier1_data)
    else:
        tier1_data = {"skipped": "No web address provided"}
        await _set_progress(audit_job_id, 30, tier1_status="skipped", tier1_result=tier1_data)

    # ---- Tier 2: mobile build ------------------------------------------------
    tier2_data: dict = {}
    if mobile_url or apk_path or ipa_path:
        await _set_progress(audit_job_id, 35, tier2_status="running")
        try:
            mobile_result = await run_mobile_audit(
                apk_path=apk_path,
                ipa_path=ipa_path,
                store_url=mobile_url,
                with_appium="appium" in outputs,
                with_manual="manual" in outputs,
            )
            if mobile_result.error and not (mobile_result.app_id or mobile_result.permissions or mobile_result.security_flags):
                raise RuntimeError(mobile_result.error)
            tier2_data = mobile_result.to_dict()
            tier2_data["appium_tests"] = mobile_result.appium_test_code
            if "security" not in outputs:
                tier2_data["security_flags"] = []
            critical += _count(tier2_data["security_flags"], "critical")
            high += _count(tier2_data["security_flags"], "high")
            tier_states.append("completed")
            await _set_progress(
                audit_job_id, 50,
                tier2_status="completed",
                tier2_result=tier2_data,
                critical_count=critical,
                high_count=high,
            )
        except Exception as e:
            tier2_data = {"error": _reason(e)}
            tier_states.append("failed")
            await _set_progress(audit_job_id, 50, tier2_status="failed", tier2_result=tier2_data)
    else:
        tier2_data = {"skipped": "No mobile build provided"}
        await _set_progress(audit_job_id, 50, tier2_status="skipped", tier2_result=tier2_data)

    # ---- Tier 3: API and security checks --------------------------------------
    tier3_data: dict = {}
    if target_url and "security" in outputs:
        await _set_progress(audit_job_id, 55, tier3_status="running")
        try:
            # API paths hang off the site root, not off whichever page the user pasted.
            parts = urlparse(target_url)
            api_result = await run_api_audit(f"{parts.scheme}://{parts.netloc}", discover_subdomains=depth != "quick", scan_js=True)
            tier3_data = api_result.to_dict()
            # What the crawl itself showed: transport, cookies, forms, and input written back into pages.
            seen = tier1_data.get("pages") or []
            extra = web_checks.passive(seen, crawl_report.get("cookies") or [], target_url)
            try:
                extra += await web_checks.reflected(seen)
            except Exception:
                pass          # one optional check must not lose the rest of the audit
            tier3_data["findings"] = extra + tier3_data["findings"]
            critical += _count(tier3_data["findings"], "critical")
            high += _count(tier3_data["findings"], "high")
            tier_states.append("completed")
            await _set_progress(
                audit_job_id, 70,
                tier3_status="completed",
                tier3_result=tier3_data,
                critical_count=critical,
                high_count=high,
            )
        except Exception as e:
            tier3_data = {"error": _reason(e)}
            tier_states.append("failed")
            await _set_progress(audit_job_id, 70, tier3_status="failed", tier3_result=tier3_data)
    else:
        reason = "Security audit not selected" if target_url else "No web address provided"
        tier3_data = {"skipped": reason}
        await _set_progress(audit_job_id, 70, tier3_status="skipped", tier3_result=tier3_data)

    # ---- Tier 4: manual test cases, web and mobile together -------------------
    tier4_data: dict = {}
    if "manual" in outputs:
        await _set_progress(audit_job_id, 75, tier4_status="running")
        try:
            all_manual = list(tier1_data.get("manual_test_cases", [])) + list(tier2_data.get("manual_test_cases", []))
            tier4_data = {"test_cases": all_manual, "total": len(all_manual), "jira_csv": _to_jira_csv(all_manual)}
            # Not counted in tier_states: this step only repackages the tiers above, so it
            # "succeeds" even when they all failed and must not mask that.
            await _set_progress(
                audit_job_id, 80,
                tier4_status="completed",
                tier4_result=tier4_data,
                total_test_cases=len(all_manual),
            )
        except Exception as e:
            tier4_data = {"error": _reason(e)}
            tier_states.append("failed")
            await _set_progress(audit_job_id, 80, tier4_status="failed", tier4_result=tier4_data)
    else:
        tier4_data = {"skipped": "Manual test cases not selected"}
        await _set_progress(audit_job_id, 80, tier4_status="skipped", tier4_result=tier4_data)

    await _finish(audit_job_id, tier_states, critical, high, tier1_data, tier2_data, tier3_data)


async def _run_code_audit(audit_job_id: str) -> None:
    """A scan of uploaded source code or a repository. The code is read, never run."""
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(AuditJob).where(AuditJob.id == audit_job_id))).scalar_one()
        source_type, zip_path, repo_url, label = job.source_type, job.source_path, job.repo_url, job.label
        outputs = set(job.outputs or ALL_OUTPUTS)
        depth = job.depth or "standard"
        ref, token = job.repo_ref, None
        # A pull request on a private repository is fetched with the organisation's GitHub token.
        if (job.trigger or {}).get("private"):
            from app.core.secrets import decrypt
            from app.models.integration import Integration

            row = (await db.execute(select(Integration).where(Integration.organization_id == job.organization_id, Integration.kind == "github"))).scalar_one_or_none()
            token = decrypt(row.secret_encrypted) if row else None

    await _set_progress(
        audit_job_id, 5, status=AuditStatus.running, tier1_status="running",
        tier2_status="skipped", tier2_result={"skipped": "No mobile build provided"},
    )
    tier1_data: dict = {}
    tier3_data: dict = {"skipped": "Security audit not selected"}
    tier_states: list[str] = []
    critical = high = 0
    work = None
    try:
        # ---- Tier 1: fetch the code, list files and routes, find missing tests ----
        try:
            work = await asyncio.to_thread(code_auditor.prepare_source, source_type, zip_path, repo_url, ref, token)
            scan = await asyncio.to_thread(code_auditor.scan_tree, os.path.join(work, "src"), depth, "security" in outputs)
        except Exception as e:
            tier1_data = {"error": str(e) if isinstance(e, code_auditor.SourceError) else _reason(e)}
            await _set_progress(
                audit_job_id, 100, status=AuditStatus.failed, tier1_status="failed", tier1_result=tier1_data,
                tier3_status="skipped", tier3_result={"skipped": "The code could not be read"},
                tier4_status="skipped", tier4_result={"skipped": "The code could not be read"},
                tier5_status="skipped", tier5_result={"skipped": "The code could not be read"},
                completed_at=datetime.now(timezone.utc),
            )
            return
        tier1_data = {
            "kind": "code",
            "files_scanned": scan.files_scanned,
            "truncated": scan.truncated,
            "languages": scan.languages,
            "routes": scan.routes[:500],
            "routes_found": sorted({r["path"] for r in scan.routes})[:500],
            "qa_gaps": scan.qa_gaps,
        }
        tier_states.append("completed")
        # Kept so a software bill of materials can be downloaded later.
        tier1_data["packages"] = [{"ecosystem": p.ecosystem, "name": p.name, "version": p.version, "manifest": p.manifest} for p in scan.packages[:3000]]
        await _set_progress(
            audit_job_id, 40, tier1_status="completed", tier1_result=tier1_data,
            total_pages_audited=scan.files_scanned, coverage_pct=scan.qa_gaps.get("coverage_pct"),
        )

        # ---- Tier 3: secrets, risky code, vulnerable dependencies ----
        if "security" in outputs:
            await _set_progress(audit_job_id, 45, tier3_status="running")
            try:
                dep_findings, dep_note = await code_auditor.check_dependencies(scan.packages, depth)
                findings = sorted(scan.findings + dep_findings, key=lambda f: ["critical", "high", "medium", "low"].index(f["severity"]))
                for number, finding in enumerate(findings, 1):
                    finding["id"] = f"C-{number:03d}"
                tier3_data = {"findings": findings, "dependencies": dep_note, "subdomains_found": [], "js_secrets": []}
                critical, high = _count(findings, "critical"), _count(findings, "high")
                tier_states.append("completed")
                await _set_progress(
                    audit_job_id, 70, tier3_status="completed", tier3_result=tier3_data,
                    critical_count=critical, high_count=high,
                )
            except Exception as e:
                tier3_data = {"error": _reason(e)}
                tier_states.append("failed")
                await _set_progress(audit_job_id, 70, tier3_status="failed", tier3_result=tier3_data)
        else:
            await _set_progress(audit_job_id, 70, tier3_status="skipped", tier3_result=tier3_data)

        # ---- Tier 4: manual test cases for the routes found ----
        if "manual" in outputs:
            await _set_progress(audit_job_id, 75, tier4_status="running")
            cases, note = await code_auditor.generate_code_test_cases(scan, label, depth)
            tier4_data = {"test_cases": cases, "total": len(cases), "jira_csv": _to_jira_csv(cases), **({"note": note} if note else {})}
            await _set_progress(audit_job_id, 80, tier4_status="completed", tier4_result=tier4_data, total_test_cases=len(cases))
        else:
            await _set_progress(audit_job_id, 80, tier4_status="skipped", tier4_result={"skipped": "Manual test cases not selected"})
    finally:
        # Customer source code is not kept: remove the working copy and the uploaded archive.
        if work:
            shutil.rmtree(work, ignore_errors=True)
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)
        await _set_progress_only(audit_job_id, source_path=None)

    await _finish(audit_job_id, tier_states, critical, high, tier1_data, {}, tier3_data)


async def _run_api_spec_audit(audit_job_id: str) -> None:
    """A scan of an API from its OpenAPI or Swagger file. With a web address given, the live API is probed too."""
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(AuditJob).where(AuditJob.id == audit_job_id))).scalar_one()
        path, target_url = job.source_path, job.target_url
        outputs = set(job.outputs or ALL_OUTPUTS)
    if await asyncio.to_thread(netguard.private_target, target_url):
        target_url = None          # the description is still read; the address is not called

    await _set_progress(audit_job_id, 5, status=AuditStatus.running, tier1_status="running",
                        tier2_status="skipped", tier2_result={"skipped": "No mobile build provided"})
    tier3_data: dict = {"skipped": "Security audit not selected"}
    tier_states: list[str] = []
    critical = high = 0
    try:
        try:
            with open(path or "", "rb") as fh:
                spec = api_spec_auditor.parse(fh.read())
        except (OSError, api_spec_auditor.SpecError) as e:
            reason = str(e) if isinstance(e, api_spec_auditor.SpecError) else "The uploaded file could not be found. Upload it again."
            skipped = {"skipped": "The API description could not be read"}
            await _set_progress(audit_job_id, 100, status=AuditStatus.failed, tier1_status="failed", tier1_result={"error": reason},
                                tier3_status="skipped", tier3_result=skipped, tier4_status="skipped", tier4_result=skipped,
                                tier5_status="skipped", tier5_result=skipped, completed_at=datetime.now(timezone.utc))
            return
        about = api_spec_auditor.overview(spec)
        tier1_data = {"api": about, "routes_found": sorted({e["path"] for e in about["endpoints"]})}
        tier_states.append("completed")
        await _set_progress(audit_job_id, 40, tier1_status="completed", tier1_result=tier1_data, total_pages_audited=about["operations"])

        if "security" in outputs:
            await _set_progress(audit_job_id, 45, tier3_status="running")
            try:
                found = api_spec_auditor.review(spec)
                live_note = "Only the description file was read. Add the API's web address to probe the running API as well."
                if target_url:
                    parts = urlparse(target_url)
                    try:
                        live = (await run_api_audit(f"{parts.scheme}://{parts.netloc}", discover_subdomains=False, scan_js=False)).to_dict()
                        found += live["findings"]
                        live_note = f"The running API at {parts.netloc} was probed as well."
                    except Exception as e:
                        live_note = f"The running API could not be probed: {_reason(e)}"
                order = ["critical", "high", "medium", "low", "info"]
                found.sort(key=lambda f: order.index(f["severity"]) if f["severity"] in order else 4)
                tier3_data = {"findings": found, "live": live_note, "subdomains_found": [], "js_secrets": []}
                critical, high = _count(found, "critical"), _count(found, "high")
                tier_states.append("completed")
                await _set_progress(audit_job_id, 70, tier3_status="completed", tier3_result=tier3_data, critical_count=critical, high_count=high)
            except Exception as e:
                tier3_data = {"error": _reason(e)}
                tier_states.append("failed")
                await _set_progress(audit_job_id, 70, tier3_status="failed", tier3_result=tier3_data)
        else:
            await _set_progress(audit_job_id, 70, tier3_status="skipped", tier3_result=tier3_data)

        if "manual" in outputs:
            cases = api_spec_auditor.test_cases(spec)
            await _set_progress(audit_job_id, 80, tier4_status="completed", total_test_cases=len(cases),
                                tier4_result={"test_cases": cases, "total": len(cases), "jira_csv": _to_jira_csv(cases)})
        else:
            await _set_progress(audit_job_id, 80, tier4_status="skipped", tier4_result={"skipped": "Manual test cases not selected"})
    finally:
        if path and os.path.exists(path):
            os.remove(path)
    await _finish(audit_job_id, tier_states, critical, high, tier1_data, {}, tier3_data)


async def _run_chatbot_audit(audit_job_id: str, secret: dict | None) -> None:
    """A scan of a chatbot or AI app: a fixed set of test messages is sent and each reply is judged."""
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(AuditJob).where(AuditJob.id == audit_job_id))).scalar_one()
        endpoint, config = job.target_url, job.chatbot_config or {}
        outputs = set(job.outputs or ALL_OUTPUTS)
    skipped = {"skipped": "The chatbot could not be reached"}
    await _set_progress(audit_job_id, 5, status=AuditStatus.running, tier1_status="running",
                        tier2_status="skipped", tier2_result={"skipped": "No mobile build provided"})

    async def progress(done: int, total: int) -> None:
        await _set_progress_only(audit_job_id, progress=5 + int(60 * done / total))

    try:
        result = await chatbot_auditor.run(endpoint, config, (secret or {}).get("header"), on_progress=progress)
    except chatbot_auditor.ChatbotError as e:
        await _set_progress(audit_job_id, 100, status=AuditStatus.failed, tier1_status="failed", tier1_result={"error": str(e)},
                            tier3_status="skipped", tier3_result=skipped, tier4_status="skipped", tier4_result=skipped,
                            tier5_status="skipped", tier5_result=skipped, completed_at=datetime.now(timezone.utc))
        return
    tier1_data = {"chatbot": result}
    await _set_progress(audit_job_id, 68, tier1_status="completed", tier1_result=tier1_data, total_pages_audited=len(result["probes"]))
    critical = high = 0
    tier3_data: dict = {"skipped": "Security audit not selected"}
    if "security" in outputs:
        found = chatbot_auditor.findings(result, endpoint)
        critical, high = _count(found, "critical"), _count(found, "high")
        tier3_data = {"findings": found, "subdomains_found": [], "js_secrets": []}
        await _set_progress(audit_job_id, 74, tier3_status="completed", tier3_result=tier3_data, critical_count=critical, high_count=high)
    else:
        await _set_progress(audit_job_id, 74, tier3_status="skipped", tier3_result=tier3_data)
    if "manual" in outputs:
        cases = chatbot_auditor.test_cases()
        await _set_progress(audit_job_id, 80, tier4_status="completed", total_test_cases=len(cases),
                            tier4_result={"test_cases": cases, "total": len(cases), "jira_csv": _to_jira_csv(cases)})
    else:
        await _set_progress(audit_job_id, 80, tier4_status="skipped", tier4_result={"skipped": "Manual test cases not selected"})
    await _finish(audit_job_id, ["completed"], critical, high, tier1_data, {}, tier3_data)


async def _finish(audit_job_id: str, tier_states: list[str], critical: int, high: int,
                  tier1_data: dict, tier2_data: dict, tier3_data: dict) -> None:
    """Tier 5 for every kind of scan: risk score, summary and the PDF report."""
    # Nothing worked, so there is nothing to report on.
    if tier_states and all(s == "failed" for s in tier_states):
        await _set_progress(
            audit_job_id, 100,
            status=AuditStatus.failed,
            tier5_status="skipped",
            tier5_result={"skipped": "Every step failed"},
            completed_at=datetime.now(timezone.utc),
        )
        return

    await _set_progress(audit_job_id, 85, tier5_status="running")
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AuditJob).where(AuditJob.id == audit_job_id))
            job = res.scalar_one_or_none()

        total_findings = len(tier3_data.get("findings", [])) + len(tier2_data.get("security_flags", []))
        a11y_critical = tier1_data.get("a11y_summary", {}).get("critical", 0)
        risk_score = min(100, critical * 20 + high * 8 + a11y_critical * 5 + min(total_findings * 2, 20))
        job.risk_score = risk_score

        # The report must not depend on the AI summary: fall back to a plain one if it fails.
        summary_error = None
        try:
            summary = await _generate_unified_summary(job)
        except Exception as e:
            summary_error = _reason(e)
            summary = _fallback_summary(job, total_findings)
        pdf_path = await _write_unified_pdf(job, summary)

        await _set_progress(
            audit_job_id, 100,
            status=AuditStatus.partial if "failed" in tier_states else AuditStatus.completed,
            tier5_status="completed",
            tier5_result={
                "executive_summary": summary,
                "risk_score": risk_score,
                "pdf_path": pdf_path,
                **({"summary_error": summary_error} if summary_error else {}),
            },
            executive_summary=summary,
            report_pdf_path=pdf_path,
            risk_score=risk_score,
            completed_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        await _set_progress(
            audit_job_id, 100,
            status=AuditStatus.partial,
            tier5_status="failed",
            tier5_result={"error": _reason(e)},
            completed_at=datetime.now(timezone.utc),
        )


def _to_jira_csv(test_cases: list[dict]) -> str:
    """Convert test cases to a Jira-importable CSV string."""
    import csv
    import io
    buf = io.StringIO()
    fieldnames = ["id", "title", "category", "priority", "preconditions", "steps", "expected_result", "jira_labels"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for tc in test_cases:
        row = dict(tc)
        row["steps"] = " | ".join(tc.get("steps", []))
        row["jira_labels"] = ",".join(tc.get("jira_labels", []))
        writer.writerow(row)
    return buf.getvalue()
