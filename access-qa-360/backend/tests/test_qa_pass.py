"""Problems found by walking the whole app with a real AI service answering, and their fixes."""
import importlib
import io
import pkgutil
import string
import zipfile
from types import SimpleNamespace

import httpx
import pytest
from httpx import AsyncClient

import app.services as services
from app.core import netguard
from app.core.config import settings
from app.services import api_auditor, code_auditor, mobile_auditor, web_auditor

API = "/api/v1"


def test_every_ai_prompt_can_be_filled_in():
    """A stray pair of braces in a prompt only fails once an AI service answers, which the other tests never reach."""
    checked = 0
    for m in pkgutil.iter_modules(services.__path__):
        module = importlib.import_module(f"app.services.{m.name}")
        for name, value in vars(module).items():
            if isinstance(value, str) and name.isupper() and ("PROMPT" in name or name == "SYSTEM"):
                fields = [f for _, f, _, _ in string.Formatter().parse(value) if f is not None]
                assert all(f.isidentifier() for f in fields), f"{m.name}.{name} has a placeholder that is not a name: {fields}"
                checked += 1
    assert checked >= 10


class Answering:
    """An AI service that is reachable and answers, unlike in the rest of the tests."""

    def __init__(self):
        self.prompts = []
        self.messages = self

    async def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="def test_it():\n    assert True")])


async def test_web_scripts_are_written_when_the_ai_answers(monkeypatch):
    ai = Answering()
    monkeypatch.setattr(web_auditor, "ai", ai)
    page = web_auditor.PageAuditResult()
    page.url, page.path, page.title = "https://shop.example.com/cart", "/cart", "Your cart"
    code = await web_auditor.generate_playwright_tests([page], "https://shop.example.com")
    assert "def test_it" in code and "`TestCart`" in ai.prompts[0]


async def test_mobile_scripts_are_written_when_the_ai_answers(monkeypatch):
    ai = Answering()
    monkeypatch.setattr(mobile_auditor, "ai", ai)
    build = mobile_auditor.MobileAuditResult()
    build.platform, build.app_name, build.app_id = "ios", "Corner Shop", "com.example.shop"
    code = await mobile_auditor.generate_appium_tests(build)
    assert "def test_it" in code and "- Platform: iOS" in ai.prompts[0] and "`TestCornerShopApp`" in ai.prompts[0]


@pytest.mark.parametrize("address", ["http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/", "http://localhost:8080/", "http://127.0.0.1/", "http://[::1]/",
                                     "http://db.internal/", "https://192.168.1.10/admin"])
async def test_a_scan_cannot_be_aimed_at_a_private_address(client: AsyncClient, auth_headers, monkeypatch, address):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", False)
    for body in ({"source_type": "web", "target_url": address, "autostart": False}, {"source_type": "api", "target_url": address}):
        r = await client.post(f"{API}/audits", headers=auth_headers, json=body)
        assert r.status_code == 422 and r.json()["detail"] == netguard.REFUSED, body


async def test_a_public_name_that_points_at_a_private_address_is_refused_when_the_scan_starts(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_TARGETS", False)
    monkeypatch.setattr(netguard.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.1.2.3", 0))])
    assert netguard.private_target("https://looks-public.example.com/") == netguard.REFUSED
    monkeypatch.setattr(netguard.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert netguard.private_target("https://looks-public.example.com/") is None
    assert netguard.private_target(None) is None


async def test_a_file_that_is_not_an_app_build_is_refused_on_upload(client: AsyncClient, auth_headers):
    def packed(*names: str) -> bytes:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for name in names:
                z.writestr(name, "x")
        return out.getvalue()

    async def upload(kind: str, name: str, content: bytes):
        job = (await client.post(f"{API}/audits", headers=auth_headers, json={"source_type": kind, "autostart": False})).json()["id"]
        return await client.post(f"{API}/audits/{job}/upload", headers=auth_headers, files={"file": (name, content, "application/octet-stream")})

    r = await upload("android", "shop.apk", b"this is not an apk")
    assert r.status_code == 422 and "cannot be opened as an app build" in r.json()["detail"]
    r = await upload("android", "shop.apk", packed("readme.txt"))
    assert r.status_code == 422 and "no AndroidManifest.xml" in r.json()["detail"]
    r = await upload("ios", "shop.ipa", packed("Payload/readme.txt"))
    assert r.status_code == 422 and "no app inside its Payload folder" in r.json()["detail"]
    assert (await upload("android", "shop.apk", packed("AndroidManifest.xml", "classes.dex"))).status_code == 200
    assert (await upload("ios", "shop.ipa", packed("Payload/Shop.app/Info.plist"))).status_code == 200


@pytest.mark.parametrize("status,reported", [(404, False), (405, False), (200, True), (401, True), (429, False)])
async def test_missing_rate_limiting_is_only_reported_for_a_sign_in_address_that_exists(status, reported):
    transport = httpx.MockTransport(lambda request: httpx.Response(status))
    async with httpx.AsyncClient(transport=transport) as http:
        results = await api_auditor.probe_rate_limiting("https://shop.example.com", "/api/v1/auth/login", http)
    assert any(isinstance(r, api_auditor.ApiAuditFinding) or (isinstance(r, dict) and r.get("check") == "rate_limiting") for r in results) is reported
    assert results[0]["verdict"] == ("rate_limited" if status == 429 else "not_rate_limited" if reported else "no_such_endpoint")


def test_secrets_are_found_inside_longer_setting_names_and_requirements_folders_are_read():
    def source(path: str, text: str):
        return code_auditor.SourceFile(path=path, text=text, language="python", is_test=False)

    found = code_auditor.find_secrets([source("settings.py", 'DB_PASSWORD = "hunter2hunter2"\nSTRIPE_API_KEY = "sk_live_abcdefgh1234"\npassword_field = "password_input"\n')])
    assert [(f["title"], f["affected_url"]) for f in found] == [("Hard-coded password in the code", "settings.py:1"), ("Hard-coded API key in the code", "settings.py:2")]
    assert all("hunter2hunter2" not in str(f) and "sk_live_abcdefgh1234" not in str(f) for f in found)

    packages = code_auditor.find_packages([source("requirements/tests.txt", "pytest==8.3.4\nfreezegun==1.5.1\n"), source("docs/notes.txt", "not==1.0\n")])
    assert sorted((p.name, p.version, p.manifest) for p in packages) == [("freezegun", "1.5.1", "requirements/tests.txt"), ("pytest", "8.3.4", "requirements/tests.txt")]


def test_website_checks_made_from_what_the_crawl_saw():
    from app.services import web_checks

    login = {"action": "http://shop.example.com/login", "method": "POST", "inputs": [{"name": "email", "type": "email"}, {"name": "password", "type": "password"}]}
    pages = [
        {"url": "http://shop.example.com/", "status_code": 200, "response_headers": {"server": "Apache/2.2.3 (CentOS)", "x-powered-by": "PHP/5.4.16"}, "forms": []},
        {"url": "http://shop.example.com/login", "status_code": 200, "response_headers": {}, "forms": [login]},
        {"url": "http://shop.example.com/admin/users", "status_code": 200, "response_headers": {}, "forms": []},
    ]
    cookies = [{"name": "session", "httpOnly": False, "secure": False, "sameSite": "None"}, {"name": "theme", "httpOnly": False, "secure": False, "sameSite": "None"}]
    found = {f["title"]: f for f in web_checks.passive(pages, cookies, "http://shop.example.com/")}
    assert set(found) == {"The site is served without encryption", "Passwords or card details are sent without encryption", "Server software and version are disclosed",
                          "Sign-in cookies are missing protective settings", "Check by hand: forms have no anti-forgery token", "Check by hand: admin pages opened without signing in"}
    assert "session (no HttpOnly, Secure, SameSite)" in found["Sign-in cookies are missing protective settings"]["description"] and "theme" not in str(found["Sign-in cookies are missing protective settings"])
    assert "Apache/2.2.3" in found["Server software and version are disclosed"]["description"] and "PHP/5.4.16" in found["Server software and version are disclosed"]["description"]

    # A site that does these things right gets none of them.
    good = [{"url": "https://shop.example.com/login", "status_code": 200, "response_headers": {"server": "nginx"},
             "forms": [{**login, "action": "https://shop.example.com/login", "inputs": login["inputs"] + [{"name": "csrf_token", "type": "hidden"}]}]}]
    assert web_checks.passive(good, [{"name": "session", "httpOnly": True, "secure": True, "sameSite": "Lax"}], "https://shop.example.com/") == []


async def test_input_written_back_into_a_page_is_reported_once_and_only_when_unescaped(monkeypatch):
    import html
    from urllib.parse import parse_qs, urlparse

    from app.services import web_checks

    def site(request: httpx.Request) -> httpx.Response:
        q = parse_qs(urlparse(str(request.url)).query)
        if request.url.path == "/search":
            return httpx.Response(200, headers={"content-type": "text/html"}, text=f"<h1>Results for {q['q'][0]}</h1>")                       # unescaped
        return httpx.Response(200, headers={"content-type": "text/html"}, text=f"<h1>Product {html.escape(q['id'][0])}</h1>")                  # escaped

    real = httpx.AsyncClient
    monkeypatch.setattr(web_checks.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(site), **kw))
    pages = [{"url": "https://shop.example.com/search?q=tea"}, {"url": "https://shop.example.com/search?q=coffee"}, {"url": "https://shop.example.com/product?id=1"}, {"url": "https://shop.example.com/"}]
    found = await web_checks.reflected(pages)
    assert [(f["title"], f["affected_url"], f["severity"]) for f in found] == [("Input is shown back on the page without escaping", "https://shop.example.com/search", "high")]


def test_a_page_the_accessibility_check_failed_on_is_not_counted_as_a_problem():
    def page(url, violations):
        p = web_auditor.PageAuditResult()
        p.url, p.a11y_violations = url, violations
        return p

    summary = web_auditor.summarise_a11y([page("https://a.example/", [{"error": "could not run"}]),
                                          page("https://a.example/x", [{"id": "image-alt", "impact": "critical", "nodes_count": 2}])])
    assert summary["pages_not_checked"] == 1 and summary["total_violations"] == 1 and [v["id"] for v in summary["violations"]] == ["image-alt"]
    assert "axe v4.9.1" in web_auditor.AXE_SOURCE[:40]
