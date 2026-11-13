"""
One flat list of everything a scan found, whatever kind of scan it was.

Each entry carries a fingerprint that stays the same from one scan of a target
to the next, so two scans can be compared: what is new, what was fixed.
"""
from __future__ import annotations

import hashlib
import re

SEVERITIES = ["critical", "high", "medium", "low", "info"]
_A11Y_SEVERITY = {"critical": "high", "serious": "medium", "moderate": "low", "minor": "low"}
_LINE = re.compile(r":\d+(:\d+)?$")


def _fingerprint(source: str, kind: str, title: str, location: str) -> str:
    # Line numbers move whenever code above them changes, so they are left out.
    where = _LINE.sub("", (location or "").strip().lower().rstrip("/"))
    raw = "|".join([source, (kind or "").lower(), re.sub(r"\s+", " ", (title or "").strip().lower()), where])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _entry(source: str, index: int, f: dict, location: str) -> dict:
    severity = str(f.get("severity") or "medium").lower()
    return {
        "source": source, "index": index,
        "severity": severity if severity in SEVERITIES else "medium",
        "title": f.get("title") or "Untitled finding",
        "description": f.get("description") or f.get("detail") or "",
        "location": location,
        "check": f.get("check") or "",
        "cwe_id": f.get("cwe_id") or "",
        "owasp_category": f.get("owasp_category") or "",
        "remediation": f.get("remediation") or "",
        "fingerprint": _fingerprint(source, f.get("check") or "", f.get("title") or "", location),
    }


def all_findings(job) -> list[dict]:
    """Security, mobile and accessibility findings of a scan, most severe first."""
    t1, t2, t3 = job.tier1_result or {}, job.tier2_result or {}, job.tier3_result or {}
    found = [_entry("security", i, f, f.get("affected_url") or "") for i, f in enumerate(t3.get("findings") or [])]
    found += [_entry("mobile", i, f, f.get("affected_url") or job.source_filename or "Mobile build") for i, f in enumerate(t2.get("security_flags") or [])]
    for i, v in enumerate((t1.get("a11y_summary") or {}).get("violations") or []):
        found.append(_entry("accessibility", i, {
            "severity": _A11Y_SEVERITY.get(v.get("impact"), "low"), "title": v.get("help") or v.get("id"),
            "description": v.get("description"), "check": v.get("id"),
            "remediation": v.get("helpUrl") or "",
        }, ""))
    for i, f in enumerate((t1.get("performance") or {}).get("findings") or []):
        found.append(_entry("performance", i, f, f.get("affected_url") or ""))
    return sorted(found, key=lambda f: SEVERITIES.index(f["severity"]))


def counts(findings: list[dict]) -> dict[str, int]:
    return {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}


def compare(before: list[dict], after: list[dict]) -> dict:
    """What `after` has that `before` did not (new), and what it no longer has (fixed)."""
    old, new = {f["fingerprint"]: f for f in before}, {f["fingerprint"]: f for f in after}
    return {
        "new": [f for key, f in new.items() if key not in old],
        "fixed": [f for key, f in old.items() if key not in new],
        "unchanged": sum(1 for key in new if key in old),
    }
