"""Scans behind a login, performance figures, API description scans, two-step sign-in and required Google sign-in."""
import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.secrets import decrypt
from app.models.audit_job import AuditJob, AuditStatus
from app.models.organization import Organization
from app.models.user import User
from app.services import api_spec_auditor, audit_orchestrator, notify, scan_control, totp, web_auditor
from tests.conftest import TestSessionLocal

API = "/api/v1"

SPEC = """
openapi: 3.0.0
info: {title: Shop API, version: "2"}
servers: [{url: "http://api.shop.example.com"}]
components:
  securitySchemes:
    bearer: {type: http, scheme: bearer}
    legacy: {type: apiKey, in: query, name: key}
paths:
  /orders/{id}:
    get: {summary: Read an order, security: [{bearer: []}], responses: {"200": {}, "401": {}, "404": {}}}
    delete: {responses: {"204": {}}}
  /login:
    post: {requestBody: {}, parameters: [{name: password, in: query}], responses: {"200": {}}}
"""


@pytest.fixture
def launched(monkeypatch):
    from app.api.routes import audits as audits_routes

    started: list[str] = []
    monkeypatch.setattr(audits_routes, "_launch", started.append)
    return started


@pytest.fixture
def test_db(monkeypatch):
    for module in (audit_orchestrator, notify):
        monkeypatch.setattr(module, "AsyncSessionLocal", TestSessionLocal)


# ---- API description scans ---------------------------------------------------

def test_api_description_review():
    spec = api_spec_auditor.parse(SPEC.encode())
    titles = {(f["title"], f["affected_url"], f["severity"]) for f in api_spec_auditor.review(spec)}
    assert ("Endpoint needs no sign-in", "DELETE /orders/{id}", "high") in titles
    assert ("The API is offered without encryption", "http://api.shop.example.com", "medium") in titles
    assert ("API key is sent in the web address", "Security scheme legacy", "medium") in titles
    assert ("Sensitive value sent in the web address", "POST /login", "medium") in titles
    assert ("No limit on sign-in attempts is documented", "POST /login", "low") in titles
    assert not any(t[0] == "Endpoint needs no sign-in" and t[1] == "POST /login" for t in titles)   # a sign-in endpoint is public on purpose
    about = api_spec_auditor.overview(spec)
    assert (about["title"], about["operations"], about["secured"]) == ("Shop API", 3, 1)
    cases = api_spec_auditor.test_cases(spec)
    assert any(c["title"] == "GET /orders/{id} refuses another user's item" for c in cases) and cases[0]["id"] == "API-001"

    for bad in (b"not: [valid", b'{"hello": "world"}', b"\xff\xfe\x00", b'{"openapi": "3.0.0", "paths": {}}'):
        with pytest.raises(api_spec_auditor.SpecError):
            api_spec_auditor.parse(bad)


async def test_an_api_description_is_scanned_end_to_end(client: AsyncClient, test_user, auth_headers, launched, test_db, monkeypatch):
    async def no_ai(*_a, **_k):
        raise RuntimeError("no AI in tests")

    monkeypatch.setattr(audit_orchestrator, "_generate_unified_summary", no_ai)
    made = await client.post(f"{API}/audits", headers=auth_headers, json={"source_type": "api", "autostart": False})
    assert made.status_code == 201
    audit = made.json()["id"]
    upload = lambda name, body: client.post(f"{API}/audits/{audit}/upload", headers=auth_headers, files={"file": (name, io.BytesIO(body), "text/plain")})
    assert (await client.post(f"{API}/audits/{audit}/start", headers=auth_headers, json={"outputs": ["security"], "ownership_confirmed": True})).status_code == 400
    assert (await upload("spec.txt", SPEC.encode())).status_code == 415
    assert (await upload("spec.yaml", b"hello: world")).status_code == 422
    ok = await upload("shop.yaml", SPEC.encode())
    assert ok.status_code == 200 and ok.json()["label"] == "Shop API" and ok.json()["allowed_outputs"] == ["security", "manual"]
    started = await client.post(f"{API}/audits/{audit}/start", headers=auth_headers, json={"outputs": ["security", "manual"], "ownership_confirmed": True})
    assert started.status_code == 200 and launched == [audit]

    await audit_orchestrator.run_audit(audit)
    job = (await client.get(f"{API}/audits/{audit}", headers=auth_headers)).json()
    assert job["status"] == "completed" and job["high_count"] == 1
    assert job["tier1_result"]["api"]["operations"] == 3
    assert any(f["title"] == "Endpoint needs no sign-in" for f in job["tier3_result"]["findings"])
    assert "Only the description file was read" in job["tier3_result"]["live"]
    assert job["total_test_cases"] == len(job["tier4_result"]["test_cases"]) > 5
    standards = (await client.get(f"{API}/audits/{audit}/standards", headers=auth_headers)).json()
    assert {c["code"]: c["count"] for c in standards["categories"]}["A07"] >= 1


# ---- scans behind a login, and performance -----------------------------------

class _App(BaseHTTPRequestHandler):
    """A tiny site: a public home page, a sign-in form, and an account page that needs the session cookie."""

    def log_message(self, *_):
        pass

    def _send(self, body: str, status=200, headers=()):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        signed_in = "session=yes" in (self.headers.get("Cookie") or "")
        if self.path == "/login":
            self._send('<form method="post" action="/login"><input type="email" name="email"><input type="password" name="password"><button>Sign in</button></form>')
        elif self.path == "/account":
            self._send('<h1>Your account</h1><a href="/logout">Sign out</a>') if signed_in else self._send("", 302, [("Location", "/login")])
        elif self.path == "/logout":
            self._send("", 302, [("Location", "/"), ("Set-Cookie", "session=; Max-Age=0")])
        else:
            self._send('<h1>Shop</h1><a href="/account">Account</a>' if signed_in else "<h1>Shop</h1>")

    def do_POST(self):
        form = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        if "email=qa%40shop.io" in form and "password=right" in form:
            self._send("", 302, [("Location", "/"), ("Set-Cookie", "session=yes; Path=/")])
        else:
            self._send('<p>Wrong details</p><form method="post" action="/login"><input type="email" name="email"><input type="password" name="password"></form>')


@pytest.fixture
def site():
    server = HTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


async def test_pages_behind_the_login_are_crawled_and_measured(site):
    report: dict = {}
    crawl = lambda login: web_auditor.crawl_and_audit(site, max_depth=2, max_pages=6, capture_screenshots=False, run_a11y=False, login=login, report=report)
    pages = await crawl({"url": f"{site}/login", "username": "qa@shop.io", "password": "right"})
    paths = {p.path for p in pages}
    assert report["login"] == "ok" and "/account" in paths and "/logout" not in paths
    home = next(p for p in pages if p.path == "/")
    assert home.performance["dom_nodes"] > 0 and home.performance["requests"] >= 1 and home.performance["ttfb_ms"] is not None
    assert web_auditor.summarise_performance(pages)["pages_measured"] == len(pages)

    pages = await crawl({"url": f"{site}/login", "username": "qa@shop.io", "password": "wrong"})
    assert report["login"] == "The app did not accept the sign-in details" and "/account" not in {p.path for p in pages}
    await crawl({"url": "http://127.0.0.1:1/login", "username": "a", "password": "b"})
    assert report["login"] == "The sign-in page must be on the site being scanned"


def test_slow_and_heavy_pages_become_findings():
    page = web_auditor.PageAuditResult()
    page.url, page.performance = "https://shop.example.com/", {"lcp_ms": 5200, "fcp_ms": 1000, "ttfb_ms": 900, "bytes": 400_000, "requests": 20, "dom_nodes": 300}
    out = web_auditor.summarise_performance([page])
    assert [(f["check"], f["severity"]) for f in out["findings"]] == [("lcp_ms", "medium"), ("ttfb_ms", "low")]
    assert "5.2 s" in out["findings"][0]["description"] and out["averages"]["lcp_ms"] == 5200


async def test_sign_in_details_are_encrypted_and_wiped_after_the_scan(client: AsyncClient, test_user, auth_headers, launched, test_db, monkeypatch):
    audit = (await client.post(f"{API}/audits", headers=auth_headers, json={"target_url": "https://shop.example.com", "autostart": False})).json()["id"]
    start = lambda login: client.post(f"{API}/audits/{audit}/start", headers=auth_headers, json={"outputs": ["security"], "ownership_confirmed": True, "login": login})
    elsewhere = await start({"url": "https://evil.example.com/login", "username": "qa", "password": "pw"})
    assert elsewhere.status_code == 422 and "on the site being scanned" in elsewhere.json()["detail"]
    assert (await start({"url": "https://shop.example.com/login", "username": "qa@shop.io", "password": "s3cret-pw"})).status_code == 200
    async with TestSessionLocal() as db:
        stored = (await db.get(AuditJob, audit)).login_encrypted
    assert "s3cret-pw" not in stored and json.loads(decrypt(stored))["password"] == "s3cret-pw"
    assert "login" not in json.dumps((await client.get(f"{API}/audits/{audit}", headers=auth_headers)).json()).replace("/login", "")

    seen = {}

    async def fake_crawl(url, **kwargs):
        seen.update(kwargs["login"])
        kwargs["report"]["login"] = "ok"
        return []

    monkeypatch.setattr(audit_orchestrator, "crawl_and_audit", fake_crawl)
    monkeypatch.setattr(audit_orchestrator, "run_api_audit", fake_crawl)
    await audit_orchestrator.run_audit(audit)
    assert seen["password"] == "s3cret-pw"
    async with TestSessionLocal() as db:
        assert (await db.get(AuditJob, audit)).login_encrypted is None


# ---- two-step sign-in --------------------------------------------------------

def test_totp_matches_the_standard_and_refuses_reuse():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"                    # the RFC 6238 test secret, "12345678901234567890"
    assert totp.code_at(secret, 59 // 30) == "287082"               # RFC 6238 test vector at T=59s (last six digits)
    step = totp.verify(secret, "287 082", None, now=59)
    assert step == 1 and totp.verify(secret, "287082", step, now=59) is None       # the same code cannot be used twice
    assert totp.verify(secret, "287082", None, now=59 + 30) == 1                     # one step late is allowed
    assert totp.verify(secret, "287082", None, now=59 + 90) is None
    assert totp.verify(secret, "000000", None, now=59) is None and totp.verify(secret, "12345", None) is None


async def test_two_step_sign_in(client: AsyncClient, test_user, auth_headers):
    login = lambda **more: client.post(f"{API}/auth/login", json={"email": "test@example.com", "password": "testpass123", **more})
    setup = (await client.post(f"{API}/auth/2fa/setup", headers=auth_headers)).json()
    assert setup["uri"].startswith("otpauth://totp/Wiseflow:test%40example.com?secret=" + setup["secret"])
    assert (await login()).status_code == 200                                            # not on until a code is confirmed
    assert (await client.post(f"{API}/auth/2fa/enable", headers=auth_headers, json={"code": "000000"})).status_code == 400
    now = int(time.time() // 30)
    assert (await client.post(f"{API}/auth/2fa/enable", headers=auth_headers, json={"code": totp.code_at(setup["secret"], now - 1)})).status_code == 200
    assert (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["two_step_enabled"] is True

    needs = await login()
    assert needs.status_code == 401 and needs.json()["detail"] == "two_step_required"
    assert (await login(code="000000")).status_code == 401
    assert (await login(code=totp.code_at(setup["secret"], now - 1))).status_code == 401    # the code used to switch it on is spent
    assert (await login(code=totp.code_at(setup["secret"], now))).status_code == 200
    assert (await client.post(f"{API}/auth/login", json={"email": "test@example.com", "password": "wrong", "code": "1"})).status_code == 401

    off = lambda **b: client.post(f"{API}/auth/2fa/disable", headers=auth_headers, json=b)
    assert (await off(password="wrong", code=totp.code_at(setup["secret"], now + 1))).status_code == 400
    assert (await off(password="testpass123", code=totp.code_at(setup["secret"], now + 1))).status_code == 200
    assert (await login()).status_code == 200
    async with TestSessionLocal() as db:
        assert (await db.get(User, test_user.id)).totp_secret_encrypted is None


# ---- required Google sign-in -------------------------------------------------

async def test_an_owner_can_require_google_sign_in_for_members(client: AsyncClient, test_user, auth_headers, monkeypatch):
    org = (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["organization_id"]
    assert (await client.patch(f"{API}/org", headers=auth_headers, json={"require_sso": True})).status_code == 400      # Google is not set up
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "g-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "g-secret")
    on = await client.patch(f"{API}/org", headers=auth_headers, json={"require_sso": True})
    assert on.status_code == 200 and on.json()["require_sso"] is True and on.json()["sso_available"] is True

    from app.core.security import create_access_token, get_password_hash

    async with TestSessionLocal() as db:
        member = User(email="member@example.com", full_name="Member", hashed_password=get_password_hash("memberpass1"), organization_id=org, org_role="admin")
        db.add(member)
        await db.commit()
    refused = await client.post(f"{API}/auth/login", json={"email": "member@example.com", "password": "memberpass1"})
    assert refused.status_code == 403 and "Google" in refused.json()["detail"]
    assert (await client.post(f"{API}/auth/login", json={"email": "test@example.com", "password": "testpass123"})).status_code == 200   # the owner still can
    admin = {"Authorization": f"Bearer {create_access_token(member.id)}"}
    assert (await client.patch(f"{API}/org", headers=admin, json={"require_sso": False})).status_code == 403
    assert (await client.patch(f"{API}/org", headers=admin, json={"name": "Renamed"})).json()["name"] == "Renamed"
