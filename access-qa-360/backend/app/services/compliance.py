"""
Sorts a scan's findings under the OWASP Top 10 (2021), with their CWE numbers.

This shows where the findings fall. It is not a certificate: a category with no
findings only means this scan found nothing there.
"""
from __future__ import annotations

import re

from app.services.findings import SEVERITIES

OWASP = {
    "A01": "Broken access control",
    "A02": "Cryptographic failures",
    "A03": "Injection",
    "A04": "Insecure design",
    "A05": "Security misconfiguration",
    "A06": "Vulnerable and outdated components",
    "A07": "Identification and authentication failures",
    "A08": "Software and data integrity failures",
    "A09": "Security logging and monitoring failures",
    "A10": "Server-side request forgery",
}

# First match wins, so the more specific categories come first.
_RULES: list[tuple[str, str]] = [
    ("A06", r"dependenc|outdated|vulnerable (package|librar|component)|\bcve-|\bghsa-"),
    ("A10", r"\bssrf\b|server.side request"),
    ("A03", r"injection|\bxss\b|cross.site scripting|\beval\b|command execution|\bsqli?\b|cwe-(79|89|78|94)\b"),
    ("A08", r"deserial|pickle|yaml\.load|integrity|subresource|unsigned"),
    ("A01", r"\bbola\b|\bidor\b|access control|authoriz|path traversal|directory traversal|\bcsrf\b|cwe-(284|285|639|22|352)\b"),
    ("A07", r"\bjwt\b|token|session|authenticat|password|credential|secret|api key|private key|rate.?limit|brute|cwe-(287|798|307|384)\b"),
    ("A02", r"\btls\b|\bssl\b|\bhsts\b|cleartext|plain.?text|weak (hash|cipher|crypto)|\bmd5\b|\bsha-?1\b|encrypt|certificate|cwe-(319|327|326|311)\b"),
    ("A05", r"header|content.security.policy|\bcsp\b|x-frame|clickjack|\bcors\b|debug|misconfig|default|exposed|listing|permission|backup|exported|cwe-(16|1021|942)\b"),
    ("A09", r"logging|\blog\b|monitoring|audit trail"),
    ("A04", r"business logic|insecure design|enumerat"),
]
_COMPILED = [(code, re.compile(pattern)) for code, pattern in _RULES]
_STATED = re.compile(r"\bA(0[1-9]|10)\b")


def category(finding: dict) -> str | None:
    """The OWASP Top 10 code for a finding, or None when it does not fit one (accessibility, performance)."""
    if finding.get("source") in ("accessibility", "performance"):
        return None
    stated = _STATED.search(str(finding.get("owasp_category") or ""))
    if stated:
        return stated.group(0)
    text = " ".join(str(finding.get(k) or "") for k in ("check", "title", "cwe_id", "description")).lower()
    for code, pattern in _COMPILED:
        if pattern.search(text):
            return code
    return None


def report(findings: list[dict]) -> dict:
    groups: dict[str, list[dict]] = {code: [] for code in OWASP}
    other: list[dict] = []
    for f in findings:
        code = category(f)
        (groups[code] if code else other).append(f)

    def brief(items: list[dict]) -> list[dict]:
        return [{k: f[k] for k in ("source", "index", "severity", "title", "location", "cwe_id")} for f in items]

    return {
        "standard": "OWASP Top 10 (2021)",
        "categories": [
            {"code": code, "name": name, "count": len(groups[code]),
             "worst": min((f["severity"] for f in groups[code]), key=SEVERITIES.index, default=None), "findings": brief(groups[code])}
            for code, name in OWASP.items()
        ],
        "other": brief([f for f in other if f["source"] not in ("accessibility", "performance")]),
        "accessibility": brief([f for f in other if f["source"] == "accessibility"]),
        "covered": sum(1 for code in OWASP if groups[code]),
    }
