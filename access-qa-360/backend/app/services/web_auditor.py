"""
Tier 1 — Full Playwright Web Audit Engine

Covers:
  1. Deep route discovery (SPA-aware, auth-aware, form enumeration)
  2. Full Playwright test suite generation (happy path + edge + error + auth)
  3. Accessibility audit (WCAG 2.1 AA via axe-core)
  4. Visual regression baseline snapshots
  5. API endpoint discovery from XHR/fetch intercepts

All results feed into the unified AuditResult which the scan_url Celery task persists.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urljoin, urldefrag

from playwright.async_api import async_playwright, Page, BrowserContext, Route, Request

from app.core.ai import ai_client
from app.core.config import settings

ai = ai_client("Web tests")

# ---------------------------------------------------------------------------
# axe-core CDN snippet (accessibility engine — injected into every page)
# ---------------------------------------------------------------------------
AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class PageAuditResult:
    def __init__(self):
        self.url: str = ""
        self.path: str = ""
        self.title: str = ""
        self.status_code: int = 200
        self.response_headers: dict = {}
        self.forms: list[dict] = []
        self.links: list[str] = []
        self.api_calls: list[dict] = []          # XHR/fetch intercepted
        self.a11y_violations: list[dict] = []    # axe-core violations
        self.screenshot_b64: str = ""            # base64 PNG
        self.error: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "path": self.path,
            "title": self.title,
            "status_code": self.status_code,
            "response_headers": self.response_headers,
            "forms": self.forms,
            "links": self.links,
            "api_calls": self.api_calls,
            "a11y_violations": self.a11y_violations,
            "screenshot_b64": self.screenshot_b64[:200] + "..." if len(self.screenshot_b64) > 200 else self.screenshot_b64,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Route crawler
# ---------------------------------------------------------------------------

async def crawl_and_audit(
    start_url: str,
    *,
    max_depth: int = 4,
    max_pages: int = 60,
    rate_limit: int = 10,
    auth_config: dict | None = None,
    include_paths: list[str] | None = None,
    exclude_paths: list[str] | None = None,
    capture_screenshots: bool = True,
    run_a11y: bool = True,
) -> list[PageAuditResult]:
    """
    Crawl a web app with Playwright and return per-page audit results.
    SPA-aware: waits for network idle, handles hash/pushState routing.
    """
    parsed_base = urlparse(start_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(start_url, 0)]
    results: list[PageAuditResult] = []
    delay = 1.0 / max(rate_limit, 1)

    def _in_scope(url: str) -> bool:
        p = urlparse(url)
        if p.netloc and p.netloc != parsed_base.netloc:
            return False
        path = p.path or "/"
        if exclude_paths:
            for ep in exclude_paths:
                if re.match(ep.replace("*", ".*"), path):
                    return False
        if include_paths:
            return any(re.match(ip.replace("*", ".*"), path) for ip in include_paths)
        return True

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-web-security"],
        )
        ctx_opts: dict[str, Any] = {
            "ignore_https_errors": True,
            "user_agent": "AccessQA360-Auditor/2.0",
            "viewport": {"width": 1280, "height": 800},
        }
        if auth_config and auth_config.get("type") == "bearer":
            ctx_opts["extra_http_headers"] = {"Authorization": f"Bearer {auth_config.get('value', '')}"}
        elif auth_config and auth_config.get("type") == "cookie":
            ctx_opts["extra_http_headers"] = {"Cookie": auth_config.get("value", "")}

        context: BrowserContext = await browser.new_context(**ctx_opts)
        if auth_config and auth_config.get("type") == "basic":
            await context.set_http_credentials({
                "username": auth_config.get("username", ""),
                "password": auth_config.get("password", ""),
            })

        page = await context.new_page()

        while queue and len(results) < max_pages:
            url, depth = queue.pop(0)
            clean_url, _ = urldefrag(url)
            if clean_url in visited or not _in_scope(clean_url):
                continue
            visited.add(clean_url)

            result = PageAuditResult()
            result.url = clean_url
            result.path = urlparse(clean_url).path or "/"

            # Intercept API calls
            api_calls: list[dict] = []
            def _on_request(req: Request):
                if req.resource_type in ("xhr", "fetch"):
                    api_calls.append({
                        "method": req.method,
                        "url": req.url,
                        "resource_type": req.resource_type,
                    })
            page.on("request", _on_request)

            resp_headers: dict = {}
            status_code = 200
            def _on_response(resp):
                try:
                    if resp.url.rstrip("/") == clean_url.rstrip("/"):
                        resp_headers.update(dict(resp.headers))
                        nonlocal status_code
                        status_code = resp.status
                except Exception:
                    pass
            page.on("response", _on_response)

            try:
                await page.goto(clean_url, wait_until="networkidle", timeout=20000)
                await asyncio.sleep(delay)

                result.title = await page.title()
                result.status_code = status_code
                result.response_headers = resp_headers
                result.api_calls = api_calls[:20]

                # Collect forms
                result.forms = await _extract_forms(page, clean_url)

                # Collect links + discover new routes
                hrefs: list[str] = await page.eval_on_selector_all(
                    "a[href]", "els => els.map(e => e.href)"
                )
                for href in hrefs:
                    abs_url, _ = urldefrag(urljoin(clean_url, href))
                    if _in_scope(abs_url) and abs_url not in visited:
                        result.links.append(abs_url)
                        if depth < max_depth:
                            queue.append((abs_url, depth + 1))

                # Also discover routes from pushState / router links
                spa_routes = await _discover_spa_routes(page, base_origin)
                for r in spa_routes:
                    if r not in visited and _in_scope(r):
                        result.links.append(r)
                        if depth < max_depth:
                            queue.append((r, depth + 1))

                # Accessibility audit
                if run_a11y:
                    result.a11y_violations = await _run_axe(page)

                # Screenshot
                if capture_screenshots:
                    png = await page.screenshot(full_page=False, type="png")
                    result.screenshot_b64 = base64.b64encode(png).decode()

            except Exception as e:
                result.error = str(e)[:300]
            finally:
                page.remove_listener("request", _on_request)
                page.remove_listener("response", _on_response)

            results.append(result)

        await context.close()
        await browser.close()

    return results


async def _extract_forms(page: Page, base_url: str) -> list[dict]:
    forms = []
    try:
        form_data = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('form')).map(f => ({
                action: f.action || '',
                method: (f.method || 'get').toUpperCase(),
                inputs: Array.from(f.querySelectorAll('input,textarea,select')).map(i => ({
                    name: i.name || i.id || '',
                    type: i.type || i.tagName.toLowerCase(),
                    required: i.required,
                    placeholder: i.placeholder || '',
                }))
            }));
        }""")
        forms = form_data or []
    except Exception:
        pass
    return forms


async def _discover_spa_routes(page: Page, base_origin: str) -> list[str]:
    """Extract route paths from JS bundle source maps and <a> tags with /path hrefs."""
    routes = []
    try:
        # Look for Next.js / React Router route patterns in the page source
        content = await page.content()
        # Match href="/path" patterns
        path_matches = re.findall(r'href=["\'](/[a-zA-Z0-9/_-]{2,50})["\']', content)
        for path in path_matches:
            routes.append(f"{base_origin}{path}")
        # Match React Router path= patterns
        route_matches = re.findall(r'path=["\'](/[a-zA-Z0-9/_:-]{2,50})["\']', content)
        for path in route_matches:
            if ":" not in path:  # Skip dynamic segments like /users/:id
                routes.append(f"{base_origin}{path}")
    except Exception:
        pass
    return list(set(routes))[:20]


async def _run_axe(page: Page) -> list[dict]:
    """Inject axe-core and run accessibility audit. Returns list of violations."""
    violations = []
    try:
        await page.add_script_tag(url=AXE_CDN)
        await asyncio.sleep(0.5)
        result = await page.evaluate("""async () => {
            const r = await axe.run(document, {
                runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'best-practice'] },
                resultTypes: ['violations']
            });
            return r.violations.slice(0, 20).map(v => ({
                id: v.id,
                impact: v.impact,
                description: v.description,
                help: v.help,
                helpUrl: v.helpUrl,
                nodes_count: v.nodes.length,
                example_html: v.nodes[0] ? v.nodes[0].html.slice(0, 200) : ''
            }));
        }""")
        violations = result or []
    except Exception as e:
        violations = [{"error": str(e)[:200]}]
    return violations


# ---------------------------------------------------------------------------
# Playwright test suite generator (Claude Sonnet)
# ---------------------------------------------------------------------------

TEST_GEN_PROMPT = """You are a senior QA engineer. Generate a complete Playwright Python test suite for this web application page.

Page: {url}
Title: {title}
Forms: {forms_json}
API calls observed: {api_calls_json}
Links / routes: {links_sample}

Generate pytest tests covering:
1. Happy path for each form (fill valid data, submit, assert success)
2. Edge cases: empty required fields, invalid email format, XSS in inputs
3. Error states: network error simulation, 404 navigation
4. Auth flows if login form detected
5. Navigation: test that links lead to correct routes

Requirements:
- Use `async def test_*` with `@pytest.mark.asyncio`
- Use `page` fixture from playwright
- Use `data-testid` selectors when possible, fall back to role/text
- Include `assert` statements with meaningful messages
- Group tests in a class named `Test{PageName}`

Return ONLY valid Python code. No markdown fences."""

MANUAL_TEST_PROMPT = """You are a QA lead. Generate manual test cases for this web page.

Page: {url}
Title: {title}
Forms: {forms_json}
Routes linked from here: {links_sample}
Accessibility issues: {a11y_summary}

Generate 8-12 manual test cases covering:
- Functional (happy path, edge cases, error handling)
- UI/UX (layout, responsiveness, loading states)
- Accessibility (keyboard nav, screen reader, contrast)
- Security (input validation, auth checks)

Return JSON array. Each item:
{{
  "id": "TC-001",
  "title": "short title",
  "category": "functional|ui|accessibility|security",
  "priority": "P1|P2|P3",
  "preconditions": "...",
  "steps": ["step 1", "step 2"],
  "expected_result": "...",
  "jira_labels": ["QA", "web", "category"]
}}

Return ONLY the JSON array."""


async def generate_playwright_tests(pages: list[PageAuditResult], base_url: str) -> str:
    """Generate a full Playwright test file covering all discovered pages."""
    # Pick top 5 most interesting pages (forms > no forms)
    sorted_pages = sorted(pages, key=lambda p: len(p.forms), reverse=True)[:5]

    all_code_parts = [
        "import pytest\nfrom playwright.async_api import Page, expect\n\n\n"
    ]

    for pg in sorted_pages:
        if pg.error:
            continue
        page_name = re.sub(r'[^a-zA-Z0-9]', '_', pg.path.strip("/") or "home").title()
        prompt = TEST_GEN_PROMPT.format(
            url=pg.url,
            title=pg.title,
            forms_json=json.dumps(pg.forms[:3], indent=2),
            api_calls_json=json.dumps(pg.api_calls[:5], indent=2),
            links_sample=json.dumps(pg.links[:5]),
        )
        try:
            msg = await ai.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            code = msg.content[0].text.strip()
            code = re.sub(r"^```[a-z]*\n?", "", code)
            code = re.sub(r"\n?```$", "", code)
            all_code_parts.append(f"\n# Tests for {pg.url}\n{code}\n")
        except Exception as e:
            all_code_parts.append(f"\n# Could not generate tests for {pg.url}: {e}\n")

    return "\n".join(all_code_parts)


async def generate_manual_test_cases(pages: list[PageAuditResult]) -> list[dict]:
    """Generate manual test cases for all pages, return flat list."""
    all_cases = []
    counter = 1

    for pg in pages[:10]:
        if pg.error:
            continue
        a11y_summary = f"{len(pg.a11y_violations)} violations: " + ", ".join(
            v.get("id", "") for v in pg.a11y_violations[:3]
        ) if pg.a11y_violations else "None"

        prompt = MANUAL_TEST_PROMPT.format(
            url=pg.url,
            title=pg.title,
            forms_json=json.dumps(pg.forms[:2], indent=2),
            links_sample=json.dumps(pg.links[:5]),
            a11y_summary=a11y_summary,
        )
        try:
            msg = await ai.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            cases = json.loads(text)
            # Re-number IDs globally
            for case in cases:
                case["id"] = f"TC-{counter:03d}"
                case["page_url"] = pg.url
                counter += 1
            all_cases.extend(cases)
        except Exception:
            pass

    return all_cases


# ---------------------------------------------------------------------------
# Accessibility summary
# ---------------------------------------------------------------------------

def summarise_a11y(pages: list[PageAuditResult]) -> dict:
    all_violations: dict[str, dict] = {}
    for pg in pages:
        for v in pg.a11y_violations:
            vid = v.get("id", "unknown")
            if vid not in all_violations:
                all_violations[vid] = {
                    "id": vid,
                    "impact": v.get("impact", ""),
                    "description": v.get("description", ""),
                    "help": v.get("help", ""),
                    "helpUrl": v.get("helpUrl", ""),
                    "occurrences": 0,
                    "affected_pages": [],
                }
            all_violations[vid]["occurrences"] += v.get("nodes_count", 1)
            all_violations[vid]["affected_pages"].append(pg.url)

    return {
        "total_violations": len(all_violations),
        "critical": sum(1 for v in all_violations.values() if v["impact"] == "critical"),
        "serious": sum(1 for v in all_violations.values() if v["impact"] == "serious"),
        "moderate": sum(1 for v in all_violations.values() if v["impact"] == "moderate"),
        "minor": sum(1 for v in all_violations.values() if v["impact"] == "minor"),
        "violations": sorted(all_violations.values(), key=lambda x: ["critical","serious","moderate","minor",""].index(x["impact"]) if x["impact"] in ["critical","serious","moderate","minor",""] else 99),
    }
