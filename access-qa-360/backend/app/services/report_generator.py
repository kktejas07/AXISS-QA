"""
Report generation service — creates JSON/PDF reports with a Claude-written executive summary.

Currently supports:
  - JSON export (always generated, the source of truth)
  - PDF via reportlab (lightweight; no LaTeX dependency)
  - executive_summary report_type: Claude Sonnet writes a 3-paragraph C-level summary

PDF fallback: if reportlab is not installed, writes the report as plain-text .pdf bytes.
"""
from __future__ import annotations

import json
import os
import tempfile
import textwrap
from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.scan import Scan
from app.models.vulnerability import Vulnerability
from app.models.qa_gap import QAGap
from app.models.report import Report, ReportFormat

ai = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

EXEC_SUMMARY_PROMPT = """You are a senior security consultant writing for a C-level audience.
Produce a concise executive summary (3 short paragraphs, max 250 words total) for this scan report.

Scan URL: {url}
Scan date: {date}
Total vulnerabilities: {total_vulns} ({critical} critical, {high} high, {medium} medium, {low} low)
QA coverage gaps: {gap_count}
Top findings:
{top_findings}

Write in plain business English. First paragraph: overall risk posture.
Second paragraph: top 3 concerns and business impact.
Third paragraph: immediate recommended actions.
Return ONLY the three paragraphs, no headers."""


async def _build_report_data(scan_id: str) -> dict[str, Any]:
    """Fetch all scan data and build a serializable dict."""
    async with AsyncSessionLocal() as db:
        s_res = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = s_res.scalar_one_or_none()
        if not scan:
            raise ValueError(f"Scan {scan_id} not found")

        v_res = await db.execute(select(Vulnerability).where(Vulnerability.scan_id == scan_id))
        vulns = v_res.scalars().all()

        g_res = await db.execute(select(QAGap).where(QAGap.scan_id == scan_id))
        gaps = g_res.scalars().all()

    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "informational": 0}
    for v in vulns:
        sev_counts[v.severity.value] = sev_counts.get(v.severity.value, 0) + 1

    top_findings = "\n".join(
        f"- [{v.severity.value.upper()}] {v.title} ({v.owasp_category or 'N/A'})"
        for v in sorted(vulns, key=lambda x: ["critical","high","medium","low","informational"].index(x.severity.value))[:5]
    ) or "No vulnerabilities detected."

    return {
        "scan_id": scan_id,
        "url": scan.url,
        "scan_type": scan.scan_type.value,
        "profile": scan.scan_profile.value if scan.scan_profile else None,
        "status": scan.status.value,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "completed_at": getattr(scan, "completed_at", None) and getattr(scan, "completed_at").isoformat(),
        "vulnerability_summary": sev_counts,
        "vulnerabilities": [
            {
                "id": v.id,
                "severity": v.severity.value,
                "title": v.title,
                "description": v.description,
                "cvss_score": v.cvss_score,
                "cwe_id": v.cwe_id,
                "affected_url": v.affected_url,
                "affected_parameter": v.affected_parameter,
                "owasp_category": v.owasp_category,
                "remediation": v.remediation,
                "status": v.status.value,
            }
            for v in vulns
        ],
        "qa_gaps": [
            {
                "id": g.id,
                "route_path": g.route_path,
                "gap_type": g.gap_type.value,
                "risk_level": g.risk_level.value,
                "description": g.description,
                "recommendation": g.recommendation,
            }
            for g in gaps
        ],
        "top_findings": top_findings,
        "total_vulnerabilities": len(vulns),
        "sev_counts": sev_counts,
        "gap_count": len(gaps),
    }


async def _generate_executive_summary(data: dict) -> str:
    prompt = EXEC_SUMMARY_PROMPT.format(
        url=data["url"],
        date=data["created_at"] or "unknown",
        total_vulns=data["total_vulnerabilities"],
        critical=data["sev_counts"].get("critical", 0),
        high=data["sev_counts"].get("high", 0),
        medium=data["sev_counts"].get("medium", 0),
        low=data["sev_counts"].get("low", 0),
        gap_count=data["gap_count"],
        top_findings=data["top_findings"],
    )
    msg = await ai.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _write_pdf(data: dict, executive_summary: str, out_path: str) -> None:
    """Write a simple PDF. Uses reportlab if available, falls back to plain text."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors

        doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(f"Security & QA Scan Report", styles["Title"]))
        story.append(Paragraph(f"URL: {data['url']}", styles["Normal"]))
        story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
        story.append(Spacer(1, 0.5*cm))

        # Executive summary
        story.append(Paragraph("Executive Summary", styles["Heading1"]))
        for para in executive_summary.split("\n\n"):
            story.append(Paragraph(para.strip(), styles["Normal"]))
            story.append(Spacer(1, 0.3*cm))

        # Vulnerability summary table
        story.append(Paragraph("Vulnerability Summary", styles["Heading1"]))
        sev = data["vulnerability_summary"]
        tdata = [["Severity", "Count"], ["Critical", sev["critical"]], ["High", sev["high"]], ["Medium", sev["medium"]], ["Low", sev["low"]], ["Informational", sev["informational"]]]
        t = Table(tdata, colWidths=[8*cm, 4*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8F7FF")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Vulnerabilities
        if data["vulnerabilities"]:
            story.append(Paragraph("Vulnerabilities", styles["Heading1"]))
            for v in data["vulnerabilities"][:30]:  # Cap PDF size
                story.append(Paragraph(f"[{v['severity'].upper()}] {v['title']}", styles["Heading3"]))
                story.append(Paragraph(v["description"][:500], styles["Normal"]))
                if v.get("remediation"):
                    story.append(Paragraph(f"<b>Remediation:</b> {v['remediation']}", styles["Normal"]))
                story.append(Spacer(1, 0.3*cm))

        doc.build(story)

    except ImportError:
        # Fallback: plain text "PDF"
        lines = [
            f"SECURITY & QA SCAN REPORT",
            f"URL: {data['url']}",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "EXECUTIVE SUMMARY",
            executive_summary,
            "",
            "VULNERABILITY SUMMARY",
            json.dumps(data["vulnerability_summary"], indent=2),
            "",
            "FINDINGS",
            json.dumps(data["vulnerabilities"], indent=2),
        ]
        with open(out_path, "w") as f:
            f.write("\n".join(lines))


async def generate_report(report_id: str) -> str:
    """
    Generate the report file for the given Report record.
    Returns the file_path where the report was written.
    Updates Report.file_path in the DB.
    """
    async with AsyncSessionLocal() as db:
        r_res = await db.execute(select(Report).where(Report.id == report_id))
        report = r_res.scalar_one_or_none()
        if not report:
            raise ValueError(f"Report {report_id} not found")
        scan_id = report.scan_id
        fmt = report.format.value
        rtype = report.report_type.value

    data = await _build_report_data(scan_id)

    # Always generate executive summary for executive_summary type
    exec_summary = ""
    if rtype == "executive_summary":
        exec_summary = await _generate_executive_summary(data)
        data["executive_summary"] = exec_summary

    from app.core.storage import storage_path
    out_path = storage_path("reports", f"report_{report_id}.{fmt}")

    if fmt == "json":
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "pdf":
        _write_pdf(data, exec_summary or "No executive summary requested.", out_path)
    elif fmt == "csv":
        import csv
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["severity","title","cvss_score","affected_url","owasp_category","status"])
            writer.writeheader()
            for v in data["vulnerabilities"]:
                writer.writerow({k: v.get(k,"") for k in ["severity","title","cvss_score","affected_url","owasp_category","status"]})
    else:
        # docx — basic text fallback
        with open(out_path, "w") as f:
            f.write(json.dumps(data, indent=2, default=str))

    # Update DB record
    async with AsyncSessionLocal() as db:
        r_res = await db.execute(select(Report).where(Report.id == report_id))
        report = r_res.scalar_one_or_none()
        if report:
            report.file_path = out_path
            await db.commit()

    return out_path
