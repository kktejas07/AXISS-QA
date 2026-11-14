"""
Security checks for a website, made from what the crawl already saw: the pages,
their forms and headers, and the cookies the site set. One check also sends a
harmless marker in a page's own address to see whether it comes back unescaped.

These sit alongside the API checks, which only look at API paths.
"""
from __future__ import annotations

import re
import uuid
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

_SENSITIVE = re.compile(r"pass|pwd|card|cvv|cvc|ssn|iban", re.I)
_TOKEN = re.compile(r"csrf|xsrf|token|nonce|authenticity", re.I)
_SESSION = re.compile(r"sess|sid|auth|token|jwt|login|remember", re.I)
_VERSION = re.compile(r"[A-Za-z][\w-]*/\d+(?:\.\d+)+")


def _finding(check: str, severity: str, title: str, description: str, url: str, fix: str, cwe: str, owasp: str, proof: str = "", method: str = "GET") -> dict:
    return {"id": str(uuid.uuid4()), "check": check, "severity": severity, "title": title, "description": description, "affected_url": url, "method": method,
            "proof_request": "", "proof_response": proof[:300], "cwe_id": cwe, "owasp_category": owasp, "remediation": fix}


def _listed(urls: list[str]) -> str:
    urls = sorted(set(urls))
    return ", ".join(urls[:5]) + (f" and {len(urls) - 5} more" if len(urls) > 5 else "")


def passive(pages: list[dict], cookies: list[dict], base_url: str) -> list[dict]:
    """Findings that need no further requests."""
    out: list[dict] = []
    http = urlparse(base_url).scheme == "http"
    if http:
        out.append(_finding("transport", "high", "The site is served without encryption",
                            "Pages are loaded over http, so anyone on the same network can read or change what visitors see and send.",
                            base_url, "Serve the whole site over https and redirect http to it.", "CWE-319", "A02:2021 Cryptographic Failures"))

    exposed = []
    for page in pages:
        for form in page.get("forms") or []:
            names = " ".join(f"{i.get('name', '')} {i.get('type', '')} {i.get('placeholder', '')}" for i in form.get("inputs") or [])
            target = form.get("action") or page.get("url", "")
            if _SENSITIVE.search(names) and (target.startswith("http://") or page.get("url", "").startswith("http://")):
                exposed.append(page.get("url", ""))
    if exposed:
        out.append(_finding("transport", "high", "Passwords or card details are sent without encryption",
                            f"A form asking for a password or card details is on an http page or sends to an http address: {_listed(exposed)}.",
                            sorted(set(exposed))[0], "Serve these pages, and the addresses their forms send to, over https only.", "CWE-319", "A02:2021 Cryptographic Failures", method="POST"))

    banners = sorted({m for page in pages for m in _VERSION.findall(str((page.get("response_headers") or {}).get("server", "")) + " " + str((page.get("response_headers") or {}).get("x-powered-by", "")))})
    if banners:
        out.append(_finding("disclosure", "low", "Server software and version are disclosed",
                            f"Response headers name the software and its version ({', '.join(banners[:4])}), which tells an attacker which known flaws to try.",
                            base_url, "Remove version numbers from the Server and X-Powered-By headers.", "CWE-200", "A05:2021 Security Misconfiguration", proof=", ".join(banners)))

    weak = []
    for cookie in cookies:
        if not _SESSION.search(cookie.get("name", "")):
            continue
        missing = [flag for flag, ok in (("HttpOnly", cookie.get("httpOnly")), ("Secure", cookie.get("secure")), ("SameSite", (cookie.get("sameSite") or "None") != "None")) if not ok]
        if missing:
            weak.append(f"{cookie['name']} (no {', '.join(missing)})")
    if weak:
        out.append(_finding("cookies", "medium", "Sign-in cookies are missing protective settings",
                            f"These cookies can be read by scripts, sent over http or sent from other sites: {'; '.join(weak[:5])}.",
                            base_url, "Set HttpOnly, Secure and SameSite=Lax (or Strict) on every cookie that identifies a signed-in person.", "CWE-614", "A05:2021 Security Misconfiguration", proof="; ".join(weak)))

    unguarded = []
    for page in pages:
        for form in page.get("forms") or []:
            if str(form.get("method", "")).upper() == "POST" and not any(_TOKEN.search(str(i.get("name", ""))) for i in form.get("inputs") or []):
                unguarded.append(page.get("url", ""))
    if unguarded:
        out.append(_finding("csrf", "low", "Check by hand: forms have no anti-forgery token",
                            f"These pages have a form that changes something but carries no hidden token: {_listed(unguarded)}. If sign-in relies on a cookie without SameSite, another site could submit the form as the visitor.",
                            sorted(set(unguarded))[0], "Add an anti-forgery token to every form that changes data, or set SameSite on the sign-in cookie.", "CWE-352", "A01:2021 Broken Access Control", method="POST"))

    open_admin = [p.get("url", "") for p in pages if re.search(r"/(admin|manage|dashboard|internal)(/|$)", urlparse(p.get("url", "")).path, re.I) and p.get("status_code") == 200]
    if open_admin:
        out.append(_finding("access", "medium", "Check by hand: admin pages opened without signing in",
                            f"The scan reached these pages without the sign-in details of an administrator: {_listed(open_admin)}. If they show real admin content, anyone can.",
                            sorted(set(open_admin))[0], "Require sign-in and an administrator role on every admin page, checked on the server.", "CWE-284", "A01:2021 Broken Access Control"))
    return out


async def reflected(pages: list[dict], limit: int = 6) -> list[dict]:
    """Put a harmless marker in each page's own address and see whether it comes back as live HTML."""
    marker = f"wf{uuid.uuid4().hex[:8]}"
    probe = f'{marker}"><i>{marker}</i>'
    seen, hits = set(), []
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, headers={"User-Agent": "Wiseflow scan"}) as client:
        for page in pages:
            parts = urlparse(page.get("url", ""))
            params = parse_qsl(parts.query, keep_blank_values=True)
            key = (parts.path, tuple(sorted(k for k, _ in params)))
            if not params or key in seen or len(seen) >= limit:
                continue
            seen.add(key)
            for name, _ in params:
                url = urlunparse(parts._replace(query=urlencode([(k, probe if k == name else v) for k, v in params])))
                try:
                    r = await client.get(url)
                except httpx.HTTPError:
                    continue
                if "html" in r.headers.get("content-type", "") and f"<i>{marker}</i>" in r.text:
                    hits.append(_finding("xss", "high", "Input is shown back on the page without escaping",
                                         f"The value of \"{name}\" in the address is written into the page as HTML. An attacker can send someone a link that runs a script on this site as that person (cross-site scripting).",
                                         urlunparse(parts._replace(query="")), "Escape every value taken from the address, a form or a cookie before writing it into a page, and add a Content-Security-Policy.",
                                         "CWE-79", "A03:2021 Injection", proof=f"{name}={probe} came back unescaped"))
                    break
    return hits
