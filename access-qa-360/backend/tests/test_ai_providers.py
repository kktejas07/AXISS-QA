"""Other AI providers with an organisation's own key, meaning-based search for Wise, and the smoke test."""
import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import ai, providers
from app.core.config import settings
from app.models.audit_job import AuditJob, AuditStatus
from app.models.organization import Organization
from app.models.user import User
from app.models.wise import WiseEmbedding
from app.services import chatbot_auditor, smoke, wise
from tests.conftest import TestSessionLocal

API = "/api/v1"
OPENAI = "https://api.openai.com/v1/chat/completions"


def reply(text="OK", **usage):
    return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 12, "completion_tokens": 3, **usage}}


# ---- providers ---------------------------------------------------------------

def test_the_model_follows_the_organisations_choice():
    assert providers.model_for("openai", "claude-haiku-4-5", "balanced", None) == "gpt-4o-mini"      # a quick model stays quick
    assert providers.model_for("openai", "claude-sonnet-4-5", "balanced", None) == "gpt-4o"
    assert providers.model_for("gemini", "claude-sonnet-4-5", "fast", None) == "gemini-2.0-flash"
    assert providers.model_for("grok", "claude-haiku-4-5", "best", None) == "grok-3"
    assert providers.model_for("openai", "claude-haiku-4-5", "best", "gpt-5-exact") == "gpt-5-exact"
    assert providers.base_url("custom", "https://llm.acme.io/v1/") == "https://llm.acme.io/v1"
    assert set(providers.PROVIDERS) >= {"anthropic", "openai", "gemini", "grok", "mistral", "deepseek", "groq", "openrouter", "custom"}


async def test_a_claude_shaped_request_is_translated_and_the_reply_comes_back_claude_shaped(httpx_mock):
    httpx_mock.add_response(url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", json=reply("Two findings."))
    message = await providers.chat("gemini", None, "g-key-0123456789abcdef", "gemini-2.0-flash", system="You are Wise.", max_tokens=300,
                                   messages=[{"role": "user", "content": [{"type": "text", "text": "How many?"}, {"type": "image", "source": {}}]}])
    assert message.content[0].text == "Two findings." and (message.usage.input_tokens, message.usage.output_tokens) == (12, 3)
    sent = httpx_mock.get_requests()[0]
    body = json.loads(sent.content)
    assert sent.headers["authorization"] == "Bearer g-key-0123456789abcdef" and body["max_tokens"] == 300 and body["model"] == "gemini-2.0-flash"
    assert body["messages"] == [{"role": "system", "content": "You are Wise."}, {"role": "user", "content": "How many?"}]

    httpx_mock.add_response(url=OPENAI, json=reply())
    await providers.chat("openai", None, "sk-0123456789abcdef", "gpt-4o", messages=[{"role": "user", "content": "hi"}], max_tokens=50)
    assert json.loads(httpx_mock.get_requests()[1].content)["max_completion_tokens"] == 50
    for status, words in ((401, "did not accept the key"), (404, "does not know that model"), (429, "out of quota"), (500, "status 500")):
        httpx_mock.add_response(url=OPENAI, status_code=status, json={})
        with pytest.raises(providers.ProviderError, match=words):
            await providers.chat("openai", None, "k", "gpt-4o", messages=[{"role": "user", "content": "hi"}])


async def test_an_organisation_switches_provider_and_every_ai_call_follows(client: AsyncClient, test_user, auth_headers, httpx_mock, monkeypatch):
    save = lambda **body: client.put(f"{API}/org/ai", headers=auth_headers, json={"quality": "balanced", **body})
    start = (await client.get(f"{API}/org/ai", headers=auth_headers)).json()
    assert start["provider"] == "anthropic" and {"id": "grok", "name": "Grok (xAI)", "fast": "grok-3-mini", "best": "grok-3"} in start["providers"]
    assert (await save(provider="openai")).status_code == 422                                        # needs its own key
    assert (await save(provider="nope", api_key="sk-0123456789abcdef")).status_code == 422
    assert (await save(provider="custom", api_key="sk-0123456789abcdef", base_url="http://10.0.0.5/v1", model="m")).status_code == 422

    httpx_mock.add_response(url=OPENAI, status_code=401, json={})
    refused = await save(provider="openai", api_key="sk-wrong-0123456789abcdef")
    assert refused.status_code == 400 and "did not accept the key" in refused.json()["detail"]
    httpx_mock.add_response(url=OPENAI, json=reply())
    saved = await save(provider="openai", api_key="sk-proj-0123456789abcdWXYZ", model="gpt-4.1")
    assert saved.status_code == 200 and (saved.json()["provider"], saved.json()["model"], saved.json()["key_ending"]) == ("openai", "gpt-4.1", "WXYZ")
    assert json.loads(httpx_mock.get_requests()[-1].content)["model"] == "gpt-4.1"                   # the key and model were tried first

    org_id = (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["organization_id"]
    async with TestSessionLocal() as db:
        assert "sk-proj" not in (await db.get(Organization, org_id)).ai_key_encrypted
        context = await ai.org_context(db, org_id)
    assert (context["provider"], context["model"]) == ("openai", "gpt-4.1")

    # A feature asks for Claude as it always has; the organisation's provider answers.
    monkeypatch.setattr(ai, "record_usage", lambda *a, **k: None)
    httpx_mock.add_response(url=OPENAI, json=reply("Summary written by another provider."))
    token = ai.ai_context.set(context)
    try:
        message = await ai.ai_client("Scan summary").messages.create(model="claude-sonnet-4-5", max_tokens=700, messages=[{"role": "user", "content": "Summarise."}])
    finally:
        ai.ai_context.reset(token)
    assert message.content[0].text.strip() == "Summary written by another provider."
    assert (await save(provider="gemini")).status_code == 422                                        # a key belongs to its provider
    back = await save(provider="anthropic", api_key="")
    assert (back.json()["provider"], back.json()["own_key"], back.json()["model"]) == ("anthropic", False, None)


# ---- meaning-based search ----------------------------------------------------

async def test_wise_finds_by_meaning_and_remembers_each_passage(client: AsyncClient, test_user, auth_headers, httpx_mock, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDINGS_API_KEY", "emb-key")
    org_id = (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["organization_id"]
    async with TestSessionLocal() as db:
        now = datetime.now(timezone.utc)
        db.add(AuditJob(created_by=test_user.id, organization_id=org_id, source_type="web", target_url="https://shop.example.com", status=AuditStatus.completed, created_at=now, started_at=now,
                        tier3_result={"findings": [{"title": "No rate limiting on login", "severity": "high", "description": "Repeated attempts are not slowed."},
                                                   {"title": "Missing HSTS header", "severity": "low", "description": "Transport security is not enforced."}]}))
        await db.commit()

    def embeddings(request):
        import httpx

        texts = json.loads(request.content)["input"]
        # A stand-in for meaning: texts about sign-in attempts point one way, everything else another.
        vector = lambda t: [1.0, 0.0] if any(w in t.lower() for w in ("rate limiting", "guessing passwords")) else [0.0, 1.0]
        return httpx.Response(200, json={"data": [{"index": i, "embedding": vector(t)} for i, t in enumerate(texts)]})

    httpx_mock.add_callback(embeddings, url="https://api.openai.com/v1/embeddings", is_reusable=True)
    ask = lambda q: client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": q}]})
    data = (await ask("How do I stop people guessing passwords?")).json()        # shares no words with the finding
    assert data["search"] == "meaning" and data["sources"][0]["title"] == "High: No rate limiting on login"
    calls = len(httpx_mock.get_requests())
    async with TestSessionLocal() as db:
        stored = len((await db.execute(select(WiseEmbedding))).scalars().all())
    assert stored == 3                                                               # the scan summary and two findings
    await ask("How do I stop people guessing passwords?")
    assert len(httpx_mock.get_requests()) == calls + 1                               # only the question is embedded the second time

    httpx_mock.reset()
    httpx_mock.add_response(url="https://api.openai.com/v1/embeddings", status_code=500, json={}, is_reusable=True)
    fallback = (await ask("Tell me about the HSTS header")).json()
    assert fallback["search"] == "words" and fallback["sources"][0]["title"] == "Low: Missing HSTS header"


def test_embeddings_come_from_the_organisations_provider_when_it_has_them(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDINGS_API_KEY", "")
    assert wise.embeddings_config({}) is None and wise.embeddings_config({"provider": "grok", "api_key": "k"}) is None
    assert wise.embeddings_config({"provider": "mistral", "api_key": "k"}) == {"base": "https://api.mistral.ai/v1", "key": "k", "model": "mistral-embed"}


# ---- smoke test --------------------------------------------------------------

class _Site(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        pages = {"/": (200, "<h1>Home</h1>"), "/crash": (200, "<script>throw new Error('boom')</script>"),
                 "/gone": (404, "Not here"), "/missing-file": (200, '<img src="/nope.png">')}
        status, body = pages.get(self.path, (404, ""))
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())


async def test_smoke_test_opens_each_page_and_reports_what_is_broken(client: AsyncClient, test_user, auth_headers, monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_port}"
    try:
        pages = await smoke.check_pages([f"{site}{p}" for p in ("/", "/crash", "/gone", "/missing-file")])
    finally:
        server.shutdown()
    by_path = {p["path"]: p for p in pages}
    assert by_path["/"]["verdict"] == "pass" and by_path["/"]["status"] == 200 and by_path["/"]["ms"] is not None
    assert by_path["/crash"]["verdict"] == "fail" and "boom" in by_path["/crash"]["problems"][0]
    assert by_path["/gone"]["verdict"] == "fail" and by_path["/gone"]["problems"][0] == "The server answered with status 404"
    assert by_path["/missing-file"]["verdict"] == "warn" and "nope.png" in by_path["/missing-file"]["problems"][0]

    org_id = (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["organization_id"]
    async with TestSessionLocal() as db:
        now = datetime.now(timezone.utc)
        web = AuditJob(created_by=test_user.id, organization_id=org_id, source_type="web", target_url=site, status=AuditStatus.completed, created_at=now, started_at=now,
                       tier1_result={"pages": [{"url": f"{site}/"}, {"url": f"{site}/"}, {"url": f"{site}/x", "error": "timeout"}]})
        code = AuditJob(created_by=test_user.id, organization_id=org_id, source_type="code", status=AuditStatus.completed, created_at=now, started_at=now)
        db.add_all([web, code])
        await db.commit()
    started: list = []
    monkeypatch.setattr(smoke, "start", lambda job_id, urls: started.append((job_id, urls)))
    assert (await client.post(f"{API}/audits/{code.id}/smoke-run", headers=auth_headers)).status_code == 400
    ok = await client.post(f"{API}/audits/{web.id}/smoke-run", headers=auth_headers)
    assert ok.status_code == 202 and started == [(web.id, [f"{site}/"])]              # each page once; pages that failed to load are left out
    assert (await client.get(f"{API}/audits/{web.id}", headers=auth_headers)).json()["tier1_result"]["smoke_run"]["state"] == "running"
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).org_role = "viewer"
        await db.commit()
    assert (await client.post(f"{API}/audits/{web.id}/smoke-run", headers=auth_headers)).status_code == 403
