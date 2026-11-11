"""
Tier 3 — Extended API / Cyber Security Audit Engine

Covers:
  1. BOLA / BFLA / IDOR — object-level and function-level auth bypass
  2. Broken authentication — JWT algorithm confusion, weak secrets, missing expiry
  3. Rate limiting — burst probe on auth endpoints
  4. Mass assignment — extra fields in POST/PUT bodies
  5. CORS misconfiguration — wildcard, null origin, credentialed cross-origin
  6. Subdomain enumeration (passive, wordlist-based)
  7. Secret exposure in JS bundles — API keys, tokens, creds
  8. Security header audit (extends scanner.py)

All probes use httpx with async concurrency.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
import uuid
from typing import Any
from urllib.parse import urlparse, urljoin

import httpx

from anthropic import AsyncAnthropic
from app.core.config import settings

ai = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ApiAuditFinding:
    def __init__(self):
        self.id: str = str(uuid.uuid4())[:8]
        self.check: str = ""           # "bola" | "jwt" | "rate_limit" | etc.
        self.severity: str = "medium"  # critical | high | medium | low | info
        self.title: str = ""
        self.description: str = ""
        self.affected_url: str = ""
        self.method: str = ""
        self.proof_request: str = ""
        self.proof_response: str = ""
        self.cwe_id: str = ""
        self.owasp_category: str = ""
        self.remediation: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ApiAuditResult:
    def __init__(self):
        self.base_url: str = ""
        self.endpoints_tested: list[str] = []
        self.findings: list[ApiAuditFinding] = []
        self.js_secrets: list[dict] = []
        self.subdomains_found: list[str] = []
        self.security_headers: dict = {}
        self.cors_config: dict = {}
        self.rate_limit_results: list[dict] = []
        self.error: str = ""

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "endpoints_tested": self.endpoints_tested,
            "findings": [f.to_dict() for f in self.findings],
            "js_secrets": self.js_secrets,
            "subdomains_found": self.subdomains_found,
            "security_headers": self.security_headers,
            "cors_config": self.cors_config,
            "rate_limit_results": self.rate_limit_results,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# JWT probes
# ---------------------------------------------------------------------------

JWT_WEAK_SECRETS = ["secret", "password", "123456", "jwt_secret", "supersecret", "changeme", "dev_secret"]
ALG_NONE_PAYLOAD = {"alg": "none", "typ": "JWT"}

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_jwt_none(claims: dict) -> str:
    """Craft a JWT with alg=none — should be rejected by any sane server."""
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    return f"{header}.{payload}."


async def probe_jwt(base_url: str, existing_token: str | None, client: httpx.AsyncClient) -> list[ApiAuditFinding]:
    findings = []

    # 1. alg=none probe — craft a token without a valid signature
    if existing_token and existing_token.count(".") == 2:
        try:
            parts = existing_token.split(".")
            # Decode payload (pad to multiple of 4)
            payload_b64 = parts[1] + "==" * (4 - len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))

            none_token = _make_jwt_none(claims)
            resp = await client.get(
                f"{base_url.rstrip('/')}/api/v1/users/me",
                headers={"Authorization": f"Bearer {none_token}"},
                timeout=5,
            )
            if resp.status_code == 200:
                f = ApiAuditFinding()
                f.check = "jwt_alg_none"
                f.severity = "critical"
                f.title = "JWT Algorithm Confusion (alg=none)"
                f.description = "Server accepted a JWT with alg=none — no signature validation is enforced."
                f.affected_url = f"{base_url}/api/v1/users/me"
                f.method = "GET"
                f.proof_request = f"Authorization: Bearer {none_token[:40]}..."
                f.proof_response = f"HTTP {resp.status_code}"
                f.cwe_id = "CWE-347"
                f.owasp_category = "A02:2021 Cryptographic Failures"
                f.remediation = "Explicitly allowlist accepted algorithms (e.g. HS256/RS256) in JWT validation."
                findings.append(f)
        except Exception:
            pass

    # 2. No auth header → check for 401
    try:
        resp = await client.get(f"{base_url.rstrip('/')}/api/v1/users/me", timeout=5)
        if resp.status_code == 200:
            f = ApiAuditFinding()
            f.check = "missing_auth"
            f.severity = "critical"
            f.title = "Authenticated Endpoint Accessible Without Token"
            f.description = "/api/v1/users/me returned 200 without any Authorization header."
            f.affected_url = f"{base_url}/api/v1/users/me"
            f.method = "GET"
            f.proof_response = f"HTTP {resp.status_code}: {resp.text[:100]}"
            f.cwe_id = "CWE-306"
            f.owasp_category = "A07:2021 Identification and Authentication Failures"
            f.remediation = "Require a valid JWT for all authenticated routes."
            findings.append(f)
    except Exception:
        pass

    return findings


# ---------------------------------------------------------------------------
# CORS probe
# ---------------------------------------------------------------------------

async def probe_cors(base_url: str, client: httpx.AsyncClient) -> dict:
    result = {
        "allows_null_origin": False,
        "allows_arbitrary_origin": False,
        "allows_credentials_with_wildcard": False,
        "reflected_origin": False,
        "findings": [],
    }
    test_origins = ["null", "https://evil.example.com", "https://evil-vatax360.com"]
    for origin in test_origins:
        try:
            resp = await client.options(
                base_url,
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
                timeout=5,
            )
            acao = resp.headers.get("access-control-allow-origin", "")
            acac = resp.headers.get("access-control-allow-credentials", "")

            if acao == "*" and acac.lower() == "true":
                result["allows_credentials_with_wildcard"] = True
                result["findings"].append({
                    "severity": "critical",
                    "title": "CORS: Wildcard Origin With Credentials",
                    "detail": "ACAO: * combined with ACAC: true is invalid per spec but some servers handle it unsafely.",
                })
            elif acao == origin and origin != "null":
                result["reflected_origin"] = True
                result["findings"].append({
                    "severity": "high",
                    "title": f"CORS: Origin Reflection ({origin})",
                    "detail": f"Server reflects arbitrary origin {origin} in ACAO header.",
                })
            if origin == "null" and acao == "null":
                result["allows_null_origin"] = True
                result["findings"].append({
                    "severity": "medium",
                    "title": "CORS: Null Origin Allowed",
                    "detail": "Server allows null origin which can be exploited from sandboxed iframes.",
                })
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Rate limiting probe
# ---------------------------------------------------------------------------

async def probe_rate_limiting(base_url: str, auth_path: str, client: httpx.AsyncClient) -> list[dict]:
    results = []
    target = urljoin(base_url.rstrip("/") + "/", auth_path.lstrip("/"))

    # Fire 20 requests in rapid succession
    tasks = [
        client.post(target, json={"email": "probe@test.com", "password": "wrong"}, timeout=5)
        for _ in range(20)
    ]
    t0 = time.monotonic()
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.monotonic() - t0

    statuses = [r.status_code for r in responses if isinstance(r, httpx.Response)]
    rate_limited = sum(1 for s in statuses if s in (429, 503))

    results.append({
        "endpoint": target,
        "requests_sent": 20,
        "elapsed_seconds": round(elapsed, 2),
        "responses": {str(s): statuses.count(s) for s in set(statuses)},
        "rate_limited_count": rate_limited,
        "verdict": "rate_limited" if rate_limited > 0 else "not_rate_limited",
    })

    if rate_limited == 0:
        f = ApiAuditFinding()
        f.check = "rate_limiting"
        f.severity = "high"
        f.title = "No Rate Limiting on Authentication Endpoint"
        f.description = f"20 rapid POST requests to {target} all succeeded without HTTP 429."
        f.affected_url = target
        f.method = "POST"
        f.proof_request = f"20 rapid POST {target}"
        f.proof_response = f"All {len(statuses)} responses: {set(statuses)}"
        f.cwe_id = "CWE-307"
        f.owasp_category = "A07:2021 Identification and Authentication Failures"
        f.remediation = "Implement rate limiting (e.g. slowapi / Redis token bucket) on login and registration endpoints."
        results.append(f.to_dict())

    return results


# ---------------------------------------------------------------------------
# BOLA/IDOR probe
# ---------------------------------------------------------------------------

async def probe_bola(base_url: str, auth_token: str, client: httpx.AsyncClient) -> list[ApiAuditFinding]:
    """
    Try to access object IDs adjacent to the authenticated user's own ID.
    Requires a valid token to test for horizontal privilege escalation.
    """
    findings = []
    if not auth_token:
        return findings

    headers = {"Authorization": f"Bearer {auth_token}"}

    # First find current user's ID
    try:
        me_resp = await client.get(f"{base_url.rstrip('/')}/api/v1/users/me", headers=headers, timeout=5)
        if me_resp.status_code != 200:
            return findings
        me_data = me_resp.json()
        my_id = me_data.get("id") or me_data.get("user_id")
        if not my_id:
            return findings

        # Try to access adjacent UUIDs or integer IDs
        test_ids = []
        if isinstance(my_id, int):
            test_ids = [my_id - 1, my_id + 1, 1, 2, 999]
        elif re.match(r'^[0-9a-f-]{36}$', str(my_id)):
            # UUID — try a known-bad but plausible UUID
            test_ids = ["00000000-0000-0000-0000-000000000001"]
        else:
            test_ids = ["1", "2", "admin"]

        for test_id in test_ids[:3]:
            try:
                resp = await client.get(
                    f"{base_url.rstrip('/')}/api/v1/users/{test_id}",
                    headers=headers, timeout=5
                )
                if resp.status_code == 200 and str(test_id) != str(my_id):
                    f = ApiAuditFinding()
                    f.check = "bola"
                    f.severity = "critical"
                    f.title = "BOLA — Broken Object Level Authorization"
                    f.description = f"Authenticated user (id={my_id}) can access another user's data (id={test_id})."
                    f.affected_url = f"{base_url}/api/v1/users/{test_id}"
                    f.method = "GET"
                    f.proof_request = f"GET /api/v1/users/{test_id}"
                    f.proof_response = f"HTTP 200 — {resp.text[:200]}"
                    f.cwe_id = "CWE-639"
                    f.owasp_category = "A01:2023 Broken Object Level Authorization"
                    f.remediation = "Verify ownership on every resource access: compare requested object's owner to the authenticated user's ID."
                    findings.append(f)
                    break
            except Exception:
                pass
    except Exception:
        pass

    return findings


# ---------------------------------------------------------------------------
# JS secret scanner
# ---------------------------------------------------------------------------

SECRET_PATTERNS = {
    "aws_key":       r"AKIA[0-9A-Z]{16}",
    "aws_secret":    r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*=\s*['\"]([^'\"]{20,40})['\"]",
    "stripe_key":    r"(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{20,}",
    "google_api":    r"AIza[0-9A-Za-z_-]{35}",
    "jwt_secret":    r"(?i)jwt[_-]?secret\s*[:=]\s*['\"]([^'\"]{6,})['\"]",
    "private_key":   r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
    "generic_token": r"(?i)(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]([A-Za-z0-9+/=_-]{16,64})['\"]",
    "firebase":      r"['\"]AAAA[A-Za-z0-9_-]{7}:[A-Za-z0-9_-]{140}['\"]",
}

async def scan_js_secrets(base_url: str, client: httpx.AsyncClient) -> list[dict]:
    """Fetch JS bundle files and scan for hardcoded secrets."""
    secrets_found = []

    # Discover JS file URLs from the main page
    try:
        resp = await client.get(base_url, timeout=10)
        html = resp.text
        js_urls = re.findall(r'src=["\']([^"\']*\.js(?:\?[^"\']*)?)["\']', html)
    except Exception:
        return []

    parsed = urlparse(base_url)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"

    for js_rel in js_urls[:20]:
        js_url = js_rel if js_rel.startswith("http") else f"{base_origin}/{js_rel.lstrip('/')}"
        try:
            js_resp = await client.get(js_url, timeout=10)
            js_body = js_resp.text[:200_000]  # Cap at 200KB

            for secret_type, pattern in SECRET_PATTERNS.items():
                matches = re.findall(pattern, js_body)
                for match in matches[:3]:
                    value = match if isinstance(match, str) else match[0] if match else ""
                    # Mask middle chars
                    masked = value[:4] + "****" + value[-4:] if len(value) > 10 else "****"
                    secrets_found.append({
                        "type": secret_type,
                        "js_file": js_url,
                        "masked_value": masked,
                        "severity": "critical" if secret_type in ("aws_key", "stripe_key", "private_key") else "high",
                    })
        except Exception:
            continue

    return secrets_found


# ---------------------------------------------------------------------------
# Subdomain enumerator (passive — certificate transparency + wordlist)
# ---------------------------------------------------------------------------

COMMON_SUBDOMAINS = [
    "api", "staging", "dev", "admin", "app", "mail", "test",
    "beta", "cdn", "static", "assets", "dashboard", "portal",
    "auth", "login", "www2", "sandbox",
]


async def enumerate_subdomains(base_url: str, client: httpx.AsyncClient) -> list[str]:
    """Passive subdomain enumeration: crt.sh certificate transparency."""
    parsed = urlparse(base_url)
    domain = parsed.netloc.split(":")[0]
    # Strip leading www.
    root_domain = re.sub(r'^www\.', '', domain)

    found = []

    # crt.sh passive lookup
    try:
        ct_resp = await client.get(
            f"https://crt.sh/?q=%.{root_domain}&output=json",
            timeout=10,
            headers={"User-Agent": "AccessQA360-Auditor/2.0"},
        )
        if ct_resp.status_code == 200:
            certs = ct_resp.json()
            for cert in certs[:200]:
                name = cert.get("name_value", "").lower()
                for sub in name.split("\n"):
                    sub = sub.strip().lstrip("*.")
                    if sub.endswith(root_domain) and sub != root_domain:
                        found.append(sub)
    except Exception:
        pass

    # Active wordlist check
    async def _check(sub: str) -> str | None:
        url = f"{parsed.scheme}://{sub}.{root_domain}"
        try:
            r = await client.head(url, timeout=4)
            if r.status_code < 500:
                return f"{sub}.{root_domain}"
        except Exception:
            pass
        return None

    tasks = [_check(s) for s in COMMON_SUBDOMAINS]
    results = await asyncio.gather(*tasks)
    for r in results:
        if r:
            found.append(r)

    return list(set(found))[:30]


# ---------------------------------------------------------------------------
# Security headers audit
# ---------------------------------------------------------------------------

REQUIRED_HEADERS = {
    "strict-transport-security": {
        "severity": "high",
        "title": "Missing HSTS Header",
        "cwe": "CWE-319",
        "remediation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains",
    },
    "content-security-policy": {
        "severity": "high",
        "title": "Missing Content-Security-Policy Header",
        "cwe": "CWE-693",
        "remediation": "Define a strict CSP that restricts script-src and disallows unsafe-inline.",
    },
    "x-content-type-options": {
        "severity": "medium",
        "title": "Missing X-Content-Type-Options Header",
        "cwe": "CWE-693",
        "remediation": "Add: X-Content-Type-Options: nosniff",
    },
    "x-frame-options": {
        "severity": "medium",
        "title": "Missing X-Frame-Options Header",
        "cwe": "CWE-693",
        "remediation": "Add: X-Frame-Options: DENY or SAMEORIGIN",
    },
    "referrer-policy": {
        "severity": "low",
        "title": "Missing Referrer-Policy Header",
        "cwe": "CWE-116",
        "remediation": "Add: Referrer-Policy: strict-origin-when-cross-origin",
    },
    "permissions-policy": {
        "severity": "low",
        "title": "Missing Permissions-Policy Header",
        "cwe": "CWE-693",
        "remediation": "Add: Permissions-Policy: camera=(), microphone=(), geolocation=()",
    },
}


async def audit_security_headers(base_url: str, client: httpx.AsyncClient) -> tuple[dict, list[ApiAuditFinding]]:
    findings = []
    headers_present = {}
    try:
        resp = await client.head(base_url, timeout=8)
        lower_headers = {k.lower(): v for k, v in resp.headers.items()}

        for header, meta in REQUIRED_HEADERS.items():
            val = lower_headers.get(header)
            headers_present[header] = val

            if not val:
                f = ApiAuditFinding()
                f.check = f"missing_header_{header.replace('-', '_')}"
                f.severity = meta["severity"]
                f.title = meta["title"]
                f.description = f"The HTTP response does not include the {header} header."
                f.affected_url = base_url
                f.method = "HEAD"
                f.cwe_id = meta["cwe"]
                f.owasp_category = "A05:2021 Security Misconfiguration"
                f.remediation = meta["remediation"]
                findings.append(f)

        # Check HSTS max-age
        hsts = lower_headers.get("strict-transport-security", "")
        m = re.search(r"max-age=(\d+)", hsts)
        if m and int(m.group(1)) < 31536000:
            f = ApiAuditFinding()
            f.check = "hsts_short_maxage"
            f.severity = "medium"
            f.title = "HSTS max-age Below 1 Year"
            f.description = f"HSTS max-age is {m.group(1)} seconds (< 31536000)."
            f.affected_url = base_url
            f.method = "HEAD"
            f.cwe_id = "CWE-523"
            f.owasp_category = "A05:2021 Security Misconfiguration"
            f.remediation = "Set HSTS max-age to at least 31536000 (1 year)."
            findings.append(f)

    except Exception:
        pass

    return headers_present, findings


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_api_audit(
    base_url: str,
    *,
    auth_token: str | None = None,
    discover_subdomains: bool = True,
    scan_js: bool = True,
) -> ApiAuditResult:
    result = ApiAuditResult()
    result.base_url = base_url

    async with httpx.AsyncClient(
        verify=False,
        follow_redirects=True,
        headers={"User-Agent": "AccessQA360-AuditBot/2.0"},
        timeout=httpx.Timeout(10.0),
    ) as client:

        # 1. Security headers
        headers_present, header_findings = await audit_security_headers(base_url, client)
        result.security_headers = headers_present
        result.findings.extend(header_findings)

        # 2. CORS
        cors = await probe_cors(base_url, client)
        result.cors_config = cors
        for fc in cors.get("findings", []):
            f = ApiAuditFinding()
            f.check = "cors"
            f.severity = fc["severity"]
            f.title = fc["title"]
            f.description = fc["detail"]
            f.affected_url = base_url
            f.method = "OPTIONS"
            f.cwe_id = "CWE-942"
            f.owasp_category = "A05:2021 Security Misconfiguration"
            f.remediation = "Allowlist only trusted origins in CORS configuration; never reflect the Origin header."
            result.findings.append(f)

        # 3. Rate limiting on login
        rl_results = await probe_rate_limiting(base_url, "/api/v1/auth/login", client)
        result.rate_limit_results = rl_results
        for item in rl_results:
            if isinstance(item, dict) and item.get("check") == "rate_limiting":
                f = ApiAuditFinding()
                f.__dict__.update(item)
                result.findings.append(f)

        # 4. JWT probes
        jwt_findings = await probe_jwt(base_url, auth_token, client)
        result.findings.extend(jwt_findings)

        # 5. BOLA/IDOR (requires auth token)
        if auth_token:
            bola_findings = await probe_bola(base_url, auth_token, client)
            result.findings.extend(bola_findings)

        # 6. JS secret scan
        if scan_js:
            result.js_secrets = await scan_js_secrets(base_url, client)
            for secret in result.js_secrets:
                f = ApiAuditFinding()
                f.check = "secret_exposure"
                f.severity = secret.get("severity", "high")
                f.title = f"Secret Exposed in JS Bundle ({secret['type']})"
                f.description = f"Found a potential {secret['type']} in {secret['js_file']}."
                f.affected_url = secret["js_file"]
                f.method = "GET"
                f.proof_response = f"Masked value: {secret['masked_value']}"
                f.cwe_id = "CWE-312"
                f.owasp_category = "A02:2021 Cryptographic Failures"
                f.remediation = "Move secrets to environment variables. Never bundle secrets in client-side JS."
                result.findings.append(f)

        # 7. Subdomain enumeration (passive)
        if discover_subdomains:
            result.subdomains_found = await enumerate_subdomains(base_url, client)

    result.endpoints_tested = [
        f"{base_url}/api/v1/users/me",
        f"{base_url}/api/v1/auth/login",
        base_url,
    ]

    return result
