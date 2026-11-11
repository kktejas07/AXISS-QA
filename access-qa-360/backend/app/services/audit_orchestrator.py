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
import tempfile
import os
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.audit_job import AuditJob, AuditStatus
from app.services.web_auditor import (
    crawl_and_audit, generate_playwright_tests, generate_manual_test_cases, summarise_a11y
)
from app.services.mobile_auditor import run_mobile_audit
from app.services.api_auditor import run_api_audit

from anthropic import AsyncAnthropic
from app.core.config import settings

ai = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

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


async def _generate_unified_summary(job: AuditJob) -> str:
    t1 = job.tier1_result or {}
    t2 = job.tier2_result or {}
    t3 = job.tier3_result or {}
    t4 = job.tier4_result or {}

    # Web stats
    pages = t1.get("pages_audited", 0)
    a11y = t1.get("a11y_summary", {})
    pw_test_count = len(t1.get("playwright_tests", "").split("\ndef test_"))

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
        app_name=job.app_name or job.target_url,
        url=job.target_url,
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
    fd, path = tempfile.mkstemp(suffix=".pdf", prefix=f"audit_{job.id}_")
    os.close(fd)

    t1 = job.tier1_result or {}
    t3 = job.tier3_result or {}

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib import colors

        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        # Cover
        story.append(Paragraph("Application Audit Report", styles["Title"]))
        story.append(Paragraph(f"Target: {job.target_url}", styles["Normal"]))
        story.append(Paragraph(f"App: {job.app_name or '—'}", styles["Normal"]))
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
            f"Pages Audited: {job.total_pages_audited} · Test Cases: {job.total_test_cases}",
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
                story.append(Paragraph(f.get("description","")[:400], styles["Normal"]))
                if f.get("remediation"):
                    story.append(Paragraph(f"<b>Remediation:</b> {f['remediation']}", styles["Normal"]))
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
            f"Target: {job.target_url}",
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

async def run_audit(audit_job_id: str):
    """
    Run all 5 audit tiers for the given AuditJob.
    Updates the DB record throughout.
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
        auth_config = None  # TODO: pass through from job

    await _set_progress(audit_job_id, 5, status=AuditStatus.running, tier1_status="running")

    # ---- Tier 1: Web Audit ------------------------------------------------
    tier1_data = {}
    try:
        pages = await crawl_and_audit(
            target_url,
            max_depth=3,
            max_pages=40,
            capture_screenshots=True,
            run_a11y=True,
        )
        playwright_tests = await generate_playwright_tests(pages, target_url)
        manual_cases = await generate_manual_test_cases(pages)
        a11y_summary = summarise_a11y(pages)
        tier1_data = {
            "pages_audited": len(pages),
            "pages": [p.to_dict() for p in pages[:20]],
            "a11y_summary": a11y_summary,
            "playwright_tests": playwright_tests,
            "manual_test_cases": manual_cases,
            "routes_found": list({p.path for p in pages}),
        }
        await _set_progress(
            audit_job_id, 30,
            tier1_status="completed",
            tier1_result=tier1_data,
            total_pages_audited=len(pages),
            total_test_cases=len(manual_cases),
        )
    except Exception as e:
        tier1_data = {"error": str(e)}
        await _set_progress(audit_job_id, 30, tier1_status="failed", tier1_result=tier1_data)

    # ---- Tier 2: Mobile Audit ---------------------------------------------
    await _set_progress(audit_job_id, 35, tier2_status="running")
    tier2_data = {}
    if mobile_url or apk_path or ipa_path:
        try:
            mobile_result = await run_mobile_audit(
                apk_path=apk_path,
                ipa_path=ipa_path,
                store_url=mobile_url,
            )
            tier2_data = mobile_result.to_dict()
            tier2_data["appium_tests"] = mobile_result.appium_test_code
            await _set_progress(
                audit_job_id, 50,
                tier2_status="completed",
                tier2_result=tier2_data,
            )
        except Exception as e:
            tier2_data = {"error": str(e)}
            await _set_progress(audit_job_id, 50, tier2_status="failed", tier2_result=tier2_data)
    else:
        tier2_data = {"skipped": "No mobile input provided"}
        await _set_progress(audit_job_id, 50, tier2_status="skipped", tier2_result=tier2_data)

    # ---- Tier 3: API/Cyber Security ----------------------------------------
    await _set_progress(audit_job_id, 55, tier3_status="running")
    tier3_data = {}
    try:
        api_result = await run_api_audit(target_url, discover_subdomains=True, scan_js=True)
        tier3_data = api_result.to_dict()
        critical_count = sum(1 for f in api_result.findings if f.severity == "critical")
        high_count = sum(1 for f in api_result.findings if f.severity == "high")
        await _set_progress(
            audit_job_id, 70,
            tier3_status="completed",
            tier3_result=tier3_data,
            critical_count=critical_count,
            high_count=high_count,
        )
    except Exception as e:
        tier3_data = {"error": str(e)}
        await _set_progress(audit_job_id, 70, tier3_status="failed", tier3_result=tier3_data)

    # ---- Tier 4: Manual QA Checklists (from Tier 1 results) ---------------
    await _set_progress(audit_job_id, 75, tier4_status="running")
    tier4_data = {}
    try:
        all_manual = tier1_data.get("manual_test_cases", [])
        # Add mobile manual cases
        all_manual += tier2_data.get("manual_test_cases", [])
        tier4_data = {
            "test_cases": all_manual,
            "total": len(all_manual),
            "jira_csv": _to_jira_csv(all_manual),
        }
        await _set_progress(
            audit_job_id, 80,
            tier4_status="completed",
            tier4_result=tier4_data,
            total_test_cases=len(all_manual),
        )
    except Exception as e:
        tier4_data = {"error": str(e)}
        await _set_progress(audit_job_id, 80, tier4_status="failed", tier4_result=tier4_data)

    # ---- Tier 5: Unified Report -------------------------------------------
    await _set_progress(audit_job_id, 85, tier5_status="running")
    try:
        # Re-read job for final state
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AuditJob).where(AuditJob.id == audit_job_id))
            job = res.scalar_one_or_none()

        summary = await _generate_unified_summary(job)
        pdf_path = await _write_unified_pdf(job, summary)

        # Compute risk score (0-100, higher = worse)
        total_findings = len(tier3_data.get("findings", []))
        a11y_critical = tier1_data.get("a11y_summary", {}).get("critical", 0)
        risk_score = min(100, (job.critical_count or 0) * 20 + (job.high_count or 0) * 8 + a11y_critical * 5 + min(total_findings * 2, 20))

        tier5_data = {
            "executive_summary": summary,
            "risk_score": risk_score,
            "pdf_path": pdf_path,
        }

        await _set_progress(
            audit_job_id, 100,
            status=AuditStatus.completed,
            tier5_status="completed",
            tier5_result=tier5_data,
            executive_summary=summary,
            report_pdf_path=pdf_path,
            risk_score=risk_score,
            completed_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        await _set_progress(
            audit_job_id, 95,
            status=AuditStatus.partial,
            tier5_status="failed",
            tier5_result={"error": str(e)},
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
