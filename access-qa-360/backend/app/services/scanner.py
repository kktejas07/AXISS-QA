"""
Core Scan Engine — Playwright-based crawler + OWASP vulnerability detection + QA gap analysis.

Pipeline:
  1. Crawl target URL with Playwright → build sitemap
  2. Run active/passive security probes on each page/endpoint
  3. Use Claude to classify findings and generate CVSS scores
  4. Detect QA coverage gaps vs discovered routes
  5. Update Scan record with progress throughout
"""
from __future__ import annotations

import asyncio
import re
import time
import json
import uuid
from typing import Any
from urllib.parse import urlparse, urljoin, parse_qs, urldefrag

from playwright.async_api import async_playwright, Page, BrowserContext, Response
from app.core.ai import ai_client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.scan import Scan, ScanStatus
from app.models.vulnerability import Vulnerability, Severity, VulnStatus, FixEffort
from app.models.qa_gap import QAGap, GapType, RiskLevel
from app.models.test_case import TestCase

ai = ai_client("Quick scan")

# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------

async def _set_progress(scan_id: str, status: ScanStatus, progress: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if scan:
            scan.status = status
            scan.progress = progress
            await db.commit()


# ---------------------------------------------------------------------------
# Crawl
# ---------------------------------------------------------------------------

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "javascript:alert(1)",
]

SQLI_PAYLOADS = [
    "' OR '1'='1",
    "\" OR \"1\"=\"1",
    "1; DROP TABLE users--",
    "' UNION SELECT NULL--",
]

CSRF_INDICATORS = ["csrf", "xsrf", "_token", "authenticity_token"]

SECURITY_HEADERS = [
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "strict-transport-security",
    "permissions-policy",
]


async def crawl_site(
    page: Page,
    base_url: str,
    max_depth: int = 3,
    max_pages: int = 50,
    rate_limit: int = 10,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
) -> list[dict]:
    """
    Crawl a site starting at base_url, returning a list of page dicts:
      { url, path, title, forms, links, response_headers, status_code }
    """
    parsed_base = urlparse(base_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(base_url, 0)]
    pages: list[dict] = []
    delay = 1.0 / max(rate_limit, 1)

    def _in_scope(url: str) -> bool:
        p = urlparse(url)
        if p.netloc and p.netloc != parsed_base.netloc:
            return False
        path = p.path or "/"
        if exclude_paths:
            for ep in exclude_paths:
                pattern = ep.replace("*", ".*")
                if re.match(pattern, path):
                    return False
        if include_paths:
            return any(re.match(ip.replace("*", ".*"), path) for ip in include_paths)
        return True

    while queue and len(pages) < max_pages:
        url, depth = queue.pop(0)
        clean_url, _ = urldefrag(url)
        if clean_url in visited or not _in_scope(clean_url):
            continue
        visited.add(clean_url)

        try:
            resp_headers: dict = {}
            status_code = 200

            def _capture_response(response: Response):
                nonlocal resp_headers, status_code
                try:
                    if response.url == clean_url or response.url.rstrip("/") == clean_url.rstrip("/"):
                        resp_headers = dict(response.headers)
                        status_code = response.status
                except Exception:
                    pass

            page.on("response", _capture_response)
            await page.goto(clean_url, wait_until="domcontentloaded", timeout=15000)
            page.remove_listener("response", _capture_response)
            await asyncio.sleep(delay)

            title = await page.title()

            # Collect forms
            forms = []
            form_elements = await page.query_selector_all("form")
            for form_el in form_elements:
                action = await form_el.get_attribute("action") or ""
                method = (await form_el.get_attribute("method") or "get").upper()
                inputs = []
                input_els = await form_el.query_selector_all("input, textarea, select")
                for inp in input_els:
                    name = await inp.get_attribute("name") or ""
                    itype = await inp.get_attribute("type") or "text"
                    inputs.append({"name": name, "type": itype})
                forms.append({"action": action, "method": method, "inputs": inputs})

            # Collect links
            hrefs = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => e.href)"
            )
            links = []
            for href in hrefs:
                abs_url = urljoin(clean_url, href)
                abs_url, _ = urldefrag(abs_url)
                if _in_scope(abs_url) and abs_url not in visited:
                    links.append(abs_url)
                    if depth < max_depth:
                        queue.append((abs_url, depth + 1))

            pages.append({
                "url": clean_url,
                "path": urlparse(clean_url).path or "/",
                "title": title,
                "forms": forms,
                "links": links[:20],
                "response_headers": resp_headers,
                "status_code": status_code,
            })

        except Exception as e:
            # Page failed to load — still record it as a 0-status page
            pages.append({
                "url": clean_url,
                "path": urlparse(clean_url).path or "/",
                "title": "",
                "forms": [],
                "links": [],
                "response_headers": {},
                "status_code": 0,
                "error": str(e)[:200],
            })

    return pages


# ---------------------------------------------------------------------------
# Security probes
# ---------------------------------------------------------------------------

def _check_missing_headers(page_data: dict) -> list[dict]:
    """Check for missing security response headers."""
    findings = []
    headers = {k.lower(): v for k, v in page_data.get("response_headers", {}).items()}
    for header in SECURITY_HEADERS:
        if header not in headers:
            findings.append({
                "type": "missing_header",
                "header": header,
                "url": page_data["url"],
            })
    return findings


def _check_csrf(page_data: dict) -> list[dict]:
    """Check forms for missing CSRF tokens."""
    findings = []
    for form in page_data.get("forms", []):
        if form["method"] == "POST":
            input_names = [i["name"].lower() for i in form["inputs"]]
            has_csrf = any(tok in name for tok in CSRF_INDICATORS for name in input_names)
            if not has_csrf:
                action = form.get("action", page_data["url"])
                findings.append({
                    "type": "csrf",
                    "url": urljoin(page_data["url"], action) if action else page_data["url"],
                    "form_action": action,
                })
    return findings


async def _probe_xss(page: Page, page_data: dict) -> list[dict]:
    """Try reflected XSS payloads in URL query parameters."""
    findings = []
    parsed = urlparse(page_data["url"])
    params = parse_qs(parsed.query)
    if not params:
        return findings

    for param_name in list(params.keys())[:3]:  # Limit params tested
        for payload in XSS_PAYLOADS[:2]:  # Limit payloads
            try:
                test_url = page_data["url"].replace(
                    f"{param_name}={params[param_name][0]}",
                    f"{param_name}={payload}"
                )
                await page.goto(test_url, wait_until="domcontentloaded", timeout=10000)
                content = await page.content()
                if payload in content:
                    findings.append({
                        "type": "xss",
                        "url": page_data["url"],
                        "parameter": param_name,
                        "payload": payload,
                    })
                    break  # One finding per param is enough
            except Exception:
                pass
    return findings


async def _probe_sqli(page: Page, page_data: dict) -> list[dict]:
    """Check for SQL error messages from SQLi payloads in URL params."""
    findings = []
    parsed = urlparse(page_data["url"])
    params = parse_qs(parsed.query)
    if not params:
        return findings

    SQL_ERRORS = ["sql syntax", "mysql_fetch", "ora-", "pg_query", "sqlite_", "you have an error in your sql"]

    for param_name in list(params.keys())[:3]:
        for payload in SQLI_PAYLOADS[:2]:
            try:
                test_url = page_data["url"].replace(
                    f"{param_name}={params[param_name][0]}",
                    f"{param_name}={payload}"
                )
                await page.goto(test_url, wait_until="domcontentloaded", timeout=10000)
                content = (await page.content()).lower()
                if any(err in content for err in SQL_ERRORS):
                    findings.append({
                        "type": "sqli",
                        "url": page_data["url"],
                        "parameter": param_name,
                        "payload": payload,
                    })
                    break
            except Exception:
                pass
    return findings


# ---------------------------------------------------------------------------
# Claude AI classification
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """You are a security analyst. Classify these raw scan findings into structured vulnerabilities.

Target URL: {base_url}
Raw findings (JSON):
{findings_json}

For each finding, return a JSON array. Each item:
{{
  "title": "short title (max 80 chars)",
  "description": "2-3 sentence technical description",
  "severity": "critical|high|medium|low|informational",
  "cvss_score": 0.0-10.0,
  "cwe_id": "CWE-XXX or null",
  "owasp_category": "A01-A10 category name or null",
  "affected_url": "the affected URL",
  "affected_parameter": "parameter name or null",
  "proof_request": "HTTP request snippet showing the issue or null",
  "remediation": "1-2 sentence fix recommendation",
  "fix_effort": "low|medium|high"
}}

Return ONLY the JSON array. No markdown, no explanation."""

QA_GAP_PROMPT = """You are a QA engineer. Analyse these crawled pages and identify test coverage gaps.

Base URL: {base_url}
Pages discovered (paths + forms):
{pages_json}

Identify up to 15 QA gaps. For each return JSON:
{{
  "route_path": "/path",
  "gap_type": "uncovered|missing_edge_case|missing_error_state|missing_auth_check|missing_input_validation",
  "risk_level": "critical|high|medium|low",
  "description": "what is untested",
  "suggested_test": "1-sentence test idea"
}}

Return ONLY a JSON array. No markdown."""


async def _classify_findings(base_url: str, raw_findings: list[dict]) -> list[dict]:
    if not raw_findings:
        return []
    prompt = CLASSIFY_PROMPT.format(
        base_url=base_url,
        findings_json=json.dumps(raw_findings[:40], indent=2),
    )
    try:
        msg = await ai.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Strip markdown fences if present
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception as e:
        print(f"[Scanner] classify error: {e}")
        return []


async def _detect_qa_gaps(base_url: str, pages: list[dict]) -> list[dict]:
    if not pages:
        return []
    pages_summary = [{"path": p["path"], "forms": len(p["forms"]), "params": bool(urlparse(p["url"]).query)} for p in pages]
    prompt = QA_GAP_PROMPT.format(
        base_url=base_url,
        pages_json=json.dumps(pages_summary[:30], indent=2),
    )
    try:
        msg = await ai.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception as e:
        print(f"[Scanner] qa_gaps error: {e}")
        return []


# ---------------------------------------------------------------------------
# Main scan orchestrator
# ---------------------------------------------------------------------------

async def run_scan(scan_id: str) -> None:
    """Full async scan pipeline — called from the Celery task via asyncio.run()."""
    t0 = time.time()

    # Load scan config
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if not scan:
            return
        base_url = scan.url
        crawl_depth = scan.crawl_depth
        rate_limit = scan.rate_limit
        scan_type = scan.scan_type.value
        auth_config = scan.auth_config or {}
        include_paths = [p.strip() for p in (scan.scope_include or "").split(",") if p.strip()] or None
        exclude_paths = [p.strip() for p in (scan.scope_exclude or "").split(",") if p.strip()] or None
        project_id = scan.project_id

    await _set_progress(scan_id, ScanStatus.crawling, 5)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx_opts: dict[str, Any] = {
            "ignore_https_errors": True,
            "user_agent": "AccessQA360-Scanner/1.0",
        }

        # Apply auth
        if auth_config.get("type") == "bearer":
            ctx_opts["extra_http_headers"] = {"Authorization": f"Bearer {auth_config.get('value', '')}"}
        elif auth_config.get("type") == "cookie":
            ctx_opts["extra_http_headers"] = {"Cookie": auth_config.get("value", "")}

        context: BrowserContext = await browser.new_context(**ctx_opts)

        if auth_config.get("type") == "basic":
            await context.set_http_credentials({
                "username": auth_config.get("username", ""),
                "password": auth_config.get("password", ""),
            })

        page = await context.new_page()

        # --- Phase 1: Crawl ---
        await _set_progress(scan_id, ScanStatus.crawling, 15)
        pages = await crawl_site(
            page, base_url,
            max_depth=crawl_depth,
            max_pages=40,
            rate_limit=rate_limit,
            include_paths=include_paths,
            exclude_paths=exclude_paths,
        )
        await _set_progress(scan_id, ScanStatus.scanning, 35)

        # --- Phase 2: Security probes ---
        raw_findings: list[dict] = []

        for pg in pages:
            # Header checks (passive — always run)
            raw_findings.extend(_check_missing_headers(pg))
            # CSRF checks (passive)
            raw_findings.extend(_check_csrf(pg))

        if scan_type in ("active", "hybrid"):
            for pg in pages[:10]:  # Cap active probing
                raw_findings.extend(await _probe_xss(page, pg))
                raw_findings.extend(await _probe_sqli(page, pg))

        await context.close()
        await browser.close()

    await _set_progress(scan_id, ScanStatus.analyzing, 60)

    # --- Phase 3: Claude classification ---
    classified = await _classify_findings(base_url, raw_findings)

    await _set_progress(scan_id, ScanStatus.analyzing, 75)

    # --- Phase 4: QA gap analysis ---
    qa_gaps_raw = await _detect_qa_gaps(base_url, pages)

    await _set_progress(scan_id, ScanStatus.analyzing, 88)

    # --- Phase 5: Persist results ---
    severity_map = {
        "critical": Severity.critical,
        "high": Severity.high,
        "medium": Severity.medium,
        "low": Severity.low,
        "informational": Severity.informational,
    }
    effort_map = {
        "low": FixEffort.low,
        "medium": FixEffort.medium,
        "high": FixEffort.high,
    }
    gap_type_map = {
        "uncovered": GapType.uncovered,
        "missing_edge_case": GapType.missing_edge_case,
        "missing_error_state": GapType.partially_covered,
        "missing_auth_check": GapType.business_logic,
        "missing_input_validation": GapType.partially_covered,
        "partially_covered": GapType.partially_covered,
        "accessibility": GapType.accessibility,
        "business_logic": GapType.business_logic,
        "orphaned_test": GapType.orphaned_test,
    }
    risk_map = {
        "critical": RiskLevel.critical,
        "high": RiskLevel.high,
        "medium": RiskLevel.medium,
        "low": RiskLevel.low,
    }

    async with AsyncSessionLocal() as db:
        for item in classified:
            vuln = Vulnerability(
                id=str(uuid.uuid4()),
                scan_id=scan_id,
                severity=severity_map.get(item.get("severity", "low"), Severity.low),
                title=str(item.get("title", "Untitled"))[:500],
                description=str(item.get("description", "")),
                cvss_score=float(item["cvss_score"]) if item.get("cvss_score") is not None else None,
                cwe_id=item.get("cwe_id"),
                affected_url=str(item.get("affected_url", base_url))[:2048],
                affected_parameter=item.get("affected_parameter"),
                proof_request=item.get("proof_request"),
                remediation=item.get("remediation"),
                fix_effort=effort_map.get(item.get("fix_effort", "medium"), FixEffort.medium),
                owasp_category=item.get("owasp_category"),
                status=VulnStatus.open,
            )
            db.add(vuln)

        for gap in qa_gaps_raw:
            qa_gap = QAGap(
                id=str(uuid.uuid4()),
                scan_id=scan_id,
                route_path=str(gap.get("route_path", "/"))[:500],
                gap_type=gap_type_map.get(gap.get("gap_type", "uncovered"), GapType.uncovered),
                risk_level=risk_map.get(gap.get("risk_level", "medium"), RiskLevel.medium),
                description=str(gap.get("description", "")),
                recommendation=gap.get("suggested_test"),
            )
            db.add(qa_gap)

        # Mark scan complete
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if scan:
            scan.status = ScanStatus.completed
            scan.progress = 100
            from datetime import datetime, timezone
            scan.completed_at = datetime.now(timezone.utc)

        await db.commit()
