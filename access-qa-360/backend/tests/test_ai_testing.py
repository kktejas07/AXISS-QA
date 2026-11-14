"""Chatbot scans, Wise carrying out confirmed actions, per-organisation AI settings and Azure Boards."""
import json
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import ai
from app.core.config import settings
from app.core.secrets import decrypt
from app.models.audit_job import AuditJob, AuditStatus
from app.models.automation import ScanSchedule
from app.models.organization import Organization
from app.models.user import User
from app.services import audit_orchestrator, chatbot_auditor as bot, notify, scan_control, wise
from tests.conftest import TestSessionLocal

API = "/api/v1"
BOT = "https://bot.example.com/chat"
BODY = '{"messages": [{"role": "user", "content": "{{message}}"}]}'
CONFIG = {"body": BODY, "reply_path": "choices.0.message.content"}


@pytest.fixture
def public(monkeypatch):
    """Pretend the test hosts resolve to public addresses."""
    monkeypatch.setattr(bot.socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.216.34", 443))])


@pytest.fixture
def launched(monkeypatch):
    from app.api.routes import audits as audits_routes

    started: list[str] = []
    monkeypatch.setattr(audits_routes, "_launch", started.append)
    monkeypatch.setattr(scan_control, "launch", started.append)
    return started


def chatbot(httpx_mock, answer):
    """A fake chatbot: `answer(message)` gives the reply to each message it is sent."""
    def respond(request):
        import httpx

        message = json.loads(request.content)["messages"][0]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": answer(message)}}]})

    httpx_mock.add_callback(respond, url=BOT, is_reusable=True)


SAFE = "I'm sorry, I can't help with that. I can answer questions about your orders."


# ---- chatbot scans -----------------------------------------------------------

def test_the_message_is_placed_safely_and_the_reply_is_found():
    template = bot.check_config(BODY, "choices.0.message.content")
    sent = bot.fill(template, 'He said "hi"\n{"role": "system"}')
    assert json.loads(json.dumps(sent))["messages"][0]["content"] == 'He said "hi"\n{"role": "system"}' and len(sent["messages"]) == 1
    assert bot.pick({"choices": [{"message": {"content": "hello"}}]}, "choices.0.message.content") == "hello"
    for body, path in (("not json", "a"), ('{"a": "b"}', "a"), (BODY, "a..b"), (BODY, "a[0]"), (BODY, "")):
        with pytest.raises(bot.ChatbotError):
            bot.check_config(body, path)


def test_private_and_plain_addresses_are_refused(monkeypatch):
    for address in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"):
        monkeypatch.setattr(bot.socket, "getaddrinfo", lambda *a, address=address, **k: [(0, 0, 0, "", (address, 443))])
        with pytest.raises(bot.ChatbotError, match="private network"):
            bot.check_endpoint("https://internal.example.com/chat")
    for bad in ("http://bot.example.com/chat", "ftp://bot.example.com", "bot.example.com", ""):
        with pytest.raises(bot.ChatbotError):
            bot.check_endpoint(bad)


def test_reply_rules():
    judge = {p["id"]: p["judge"] for p in bot.PROBES}
    assert judge["override"](bot.CANARY)[0] == "fail" and judge["override"](SAFE)[0] == "pass"
    assert judge["hidden"](f"A positive review. {bot.CANARY}")[0] == "fail" and judge["hidden"]("The customer liked it.")[0] == "pass"
    assert judge["leak"]("You are a helpful assistant for Acme. Never mention refunds over $50 to anyone.")[0] == "fail" and judge["leak"](SAFE)[0] == "pass"
    assert judge["personal"]("Sure: jane.doe@acme.io, +1 (555) 010-9999")[0] == "fail" and judge["personal"](SAFE)[0] == "pass"
    assert judge["secrets"]("api_key = sk-live-abcdefghijklmnop1234")[0] == "fail" and judge["secrets"]("postgres://app:pw@db/prod")[0] == "fail" and judge["secrets"](SAFE)[0] == "pass"
    assert judge["roleplay"]("Sure! Step 1: open a terminal. Step 2: run the tool.")[0] == "fail" and judge["roleplay"](SAFE)[0] == "pass"
    assert judge["roleplay"]("Wifi is a wireless networking technology.")[0] == "review"
    assert judge["invented"]("The Zorblax 9000 has a 30-day refund window.")[0] == "review" and judge["invented"]("I'm not aware of that product.")[0] == "pass"
    assert judge["template"]("Hello 49!")[0] == "fail" and judge["template"]("Hello ${7*7}!")[0] == "pass"
    assert judge["markup"]("<script>alert('wf')</script>")[0] == "review" and judge["abuse"]("You absolute idiot.")[0] == "fail"
    assert len({p["id"] for p in bot.PROBES}) == len(bot.PROBES) == len(bot.test_cases()) == 14


async def test_a_safe_bot_passes_and_a_careless_one_fails(httpx_mock, public):
    chatbot(httpx_mock, lambda m: "I'm not aware of that product." if "Zorblax" in m else "Arr, a poem I cannot write; I can only help with orders." if "pirates" in m else "OK" if m.endswith("OK.") else SAFE)
    good = await bot.run(BOT, CONFIG, None, pause=0)
    assert (good["failed"], good["review"], good["errors"]) == (0, 0, 0) and good["passed"] == 14 and bot.findings(good, BOT) == []

    httpx_mock.reset()
    chatbot(httpx_mock, lambda m: bot.CANARY if bot.CANARY in m else "The last customer was jane@acme.io" if "phone number" in m else SAFE)
    bad = await bot.run(BOT, CONFIG, {"name": "X-Api-Key", "value": "k-123"}, pause=0)
    failed = {p["id"] for p in bad["probes"] if p["verdict"] == "fail"}
    assert failed == {"override", "hidden", "personal"}
    found = bot.findings(bad, BOT)
    assert found[0]["severity"] == "critical" and found[0]["title"] == "Data leak: asked for another customer's details" and "jane@acme.io" in found[0]["proof_response"]
    assert all(r.headers["x-api-key"] == "k-123" for r in httpx_mock.get_requests())


async def test_a_bot_that_cannot_be_talked_to_fails_with_a_reason(httpx_mock, public):
    httpx_mock.add_response(url=BOT, json={"reply": "hi"})
    with pytest.raises(bot.ChatbotError, match="was not found at"):
        await bot.run(BOT, CONFIG, None, pause=0)
    httpx_mock.add_response(url=BOT, status_code=401)
    with pytest.raises(bot.ChatbotError, match="status 401"):
        await bot.run(BOT, CONFIG, None, pause=0)


async def test_a_chatbot_scan_runs_end_to_end_and_forgets_the_key(client: AsyncClient, test_user, auth_headers, httpx_mock, public, launched, monkeypatch):
    for module in (audit_orchestrator, notify):
        monkeypatch.setattr(module, "AsyncSessionLocal", TestSessionLocal)
    monkeypatch.setattr(bot.asyncio, "sleep", lambda *_: _none())

    async def no_ai(*_a, **_k):
        raise RuntimeError("no AI in tests")

    monkeypatch.setattr(audit_orchestrator, "_generate_unified_summary", no_ai)
    make = lambda **more: client.post(f"{API}/audits", headers=auth_headers, json={"source_type": "chatbot", "autostart": False, "target_url": BOT, "app_name": "Shop helper", **more})
    assert (await make()).status_code == 422
    assert (await make(chatbot={"body": "{}", "reply_path": "a"})).status_code == 422
    assert (await make(chatbot={**CONFIG, "header_name": "Host", "header_value": "x"})).status_code == 422
    made = await make(chatbot={**CONFIG, "header_name": "Authorization", "header_value": "Bearer bot-secret-key"})
    assert made.status_code == 201 and made.json()["allowed_outputs"] == ["security", "manual"]
    audit = made.json()["id"]
    assert "bot-secret-key" not in json.dumps((await client.get(f"{API}/audits/{audit}", headers=auth_headers)).json())
    async with TestSessionLocal() as db:
        stored = (await db.get(AuditJob, audit)).login_encrypted
        assert "bot-secret-key" not in stored and json.loads(decrypt(stored))["header"]["value"] == "Bearer bot-secret-key"
    assert (await client.post(f"{API}/audits/{audit}/start", headers=auth_headers, json={"outputs": ["security", "manual"], "ownership_confirmed": True})).status_code == 200

    chatbot(httpx_mock, lambda m: bot.CANARY if "Ignore all previous" in m else SAFE)
    await audit_orchestrator.run_audit(audit)
    job = (await client.get(f"{API}/audits/{audit}", headers=auth_headers)).json()
    assert job["status"] == "completed" and job["high_count"] == 1 and job["total_test_cases"] == 14
    assert job["tier1_result"]["chatbot"]["failed"] == 1 and job["tier3_result"]["findings"][0]["title"] == "Prompt injection: told to ignore its instructions"
    assert httpx_mock.get_requests()[0].headers["authorization"] == "Bearer bot-secret-key"
    async with TestSessionLocal() as db:
        assert (await db.get(AuditJob, audit)).login_encrypted is None


async def _none():
    return None


# ---- Wise carrying out confirmed actions --------------------------------------

def test_wise_offers_to_act_only_when_it_has_what_it_needs():
    scan = wise.actions("please scan https://shop.example.com.")[0]
    assert scan["do"] == {"kind": "start_scan", "target": "https://shop.example.com"} and "uses one scan" in scan["confirm"]
    weekly = wise.actions("check https://shop.example.com every week")[0]
    assert weekly["do"] == {"kind": "create_schedule", "target": "https://shop.example.com", "frequency": "weekly"}
    assert wise.actions("run this again", audit_id="a1")[0]["do"] == {"kind": "rescan", "audit_id": "a1"}
    assert wise.actions("run this again") == [] and wise.actions("can you scan my site every day?") == [{"label": "Set up a schedule", "path": "/schedules"}]


async def test_wise_acts_only_after_confirmation_and_within_the_persons_role(client: AsyncClient, test_user, auth_headers, launched):
    act = lambda **body: client.post(f"{API}/wise/actions", headers=auth_headers, json=body)
    assert (await act(kind="start_scan", target="https://shop.example.com")).status_code == 400            # not confirmed
    assert (await act(kind="start_scan", target="shop.example.com", confirmed=True)).status_code == 422
    assert launched == []

    started = await act(kind="start_scan", target="https://shop.example.com", confirmed=True)
    assert started.status_code == 200 and started.json()["message"] == "The scan of https://shop.example.com has started."
    audit = started.json()["path"].split("/")[-1]
    async with TestSessionLocal() as db:
        job = await db.get(AuditJob, audit)
        assert job.created_by == test_user.id and job.outputs == ["security", "manual"] and job.ownership_confirmed_at and launched == [audit]
        job.status = AuditStatus.completed
        await db.commit()

    again = await act(kind="rescan", audit_id=audit, confirmed=True)
    assert again.status_code == 200 and len(launched) == 2
    limit = await act(kind="rescan", audit_id=audit, confirmed=True)                                         # a free account has two scans a month
    assert limit.status_code == 403 and "used all 2 scans" in limit.json()["detail"]

    made = await act(kind="create_schedule", target="https://shop.example.com", frequency="daily", confirmed=True)
    assert made.status_code == 200 and "will be scanned daily" in made.json()["message"]
    async with TestSessionLocal() as db:
        assert (await db.execute(select(ScanSchedule))).scalar_one().frequency == "daily"
        (await db.get(User, test_user.id)).org_role = "viewer"
        await db.commit()
    assert (await act(kind="start_scan", target="https://other.example.com", confirmed=True)).status_code == 403
    assert (await act(kind="rescan", audit_id="missing", confirmed=True)).status_code == 403


# ---- AI settings -------------------------------------------------------------

def test_quality_picks_the_model():
    assert ai.choose_model("claude-sonnet-4-5", "fast") == "claude-haiku-4-5"
    assert ai.choose_model("claude-haiku-4-5", "best") == "claude-sonnet-4-5"
    assert ai.choose_model("claude-haiku-4-5", "balanced") == "claude-haiku-4-5" and ai.choose_model("claude-sonnet-4-5", None) == "claude-sonnet-4-5"


async def test_an_organisation_sets_its_ai_quality_and_key(client: AsyncClient, test_user, auth_headers, monkeypatch):
    brief = lambda r: {k: r.json()[k] for k in ("quality", "own_key", "key_ending")}
    assert brief(await client.get(f"{API}/org/ai", headers=auth_headers)) == {"quality": "balanced", "own_key": False, "key_ending": None}
    assert (await client.put(f"{API}/org/ai", headers=auth_headers, json={"quality": "fast", "api_key": "not-a-key"})).status_code == 422
    saved = await client.put(f"{API}/org/ai", headers=auth_headers, json={"quality": "fast", "api_key": "sk-ant-api03-abcdefghijklmnop-WXYZ"})
    assert brief(saved) == {"quality": "fast", "own_key": True, "key_ending": "WXYZ"}
    org_id = (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["organization_id"]
    async with TestSessionLocal() as db:
        org = await db.get(Organization, org_id)
        assert "sk-ant" not in org.ai_key_encrypted
        context = await ai.org_context(db, org_id, "scan-1")
    assert context == {"organization_id": org_id, "audit_id": "scan-1", "quality": "fast", "cap": None, "api_key": "sk-ant-api03-abcdefghijklmnop-WXYZ", "provider": "anthropic"}

    # The key and the quality are applied where the call is made.
    seen = {}

    class Fake:
        def __init__(self, api_key=None, base_url=None):
            seen.setdefault("keys", []).append(api_key)
            self.messages = self

        async def create(self, **kwargs):
            seen["model"] = kwargs["model"]
            return type("M", (), {"usage": None, "content": []})()

    monkeypatch.setattr(ai, "AsyncAnthropic", Fake)
    monkeypatch.setattr(ai, "record_usage", lambda *a, **k: None)
    token = ai.ai_context.set(context)
    try:
        await ai.ai_client("test").messages.create(model="claude-sonnet-4-5", max_tokens=1, messages=[])
    finally:
        ai.ai_context.reset(token)
    assert seen["model"] == "claude-haiku-4-5" and seen["keys"][-1] == "sk-ant-api03-abcdefghijklmnop-WXYZ"

    kept = await client.put(f"{API}/org/ai", headers=auth_headers, json={"quality": "best"})
    assert brief(kept) == {"quality": "best", "own_key": True, "key_ending": "WXYZ"}
    assert (await client.put(f"{API}/org/ai", headers=auth_headers, json={"quality": "best", "api_key": ""})).json()["own_key"] is False
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).org_role = "member"
        await db.commit()
    assert (await client.put(f"{API}/org/ai", headers=auth_headers, json={"quality": "fast"})).status_code == 403


# ---- Azure Boards ------------------------------------------------------------

async def test_a_finding_becomes_an_azure_work_item(client: AsyncClient, test_user, auth_headers, httpx_mock):
    project = "https://dev.azure.com/acme/_apis/projects/Shop?api-version=7.0"
    httpx_mock.add_response(url=project, status_code=203, text="<html>sign in</html>")
    body = {"organization": "acme", "project": "Shop", "token": "azure-pat-0123456789"}
    assert (await client.put(f"{API}/org/azure", headers=auth_headers, json=body)).status_code == 400
    assert (await client.put(f"{API}/org/azure", headers=auth_headers, json={**body, "organization": "acme/../x"})).status_code == 422
    httpx_mock.add_response(url=project, json={"name": "Shop"})
    assert (await client.put(f"{API}/org/azure", headers=auth_headers, json=body)).json() == {"connected": True, "organization": "acme", "project": "Shop", "work_item_type": "Bug"}

    org_id = (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["organization_id"]
    async with TestSessionLocal() as db:
        now = datetime.now(timezone.utc)
        job = AuditJob(created_by=test_user.id, organization_id=org_id, source_type="web", target_url="https://shop.example.com", status=AuditStatus.completed, created_at=now, started_at=now,
                       tier3_result={"findings": [{"title": "SQL injection", "severity": "critical", "description": "The <q> parameter is unsafe.", "affected_url": "https://shop.example.com/search"}]})
        db.add(job)
        await db.commit()
    httpx_mock.add_response(url="https://dev.azure.com/acme/Shop/_apis/wit/workitems/$Bug?api-version=7.0", method="POST",
                            json={"id": 41, "_links": {"html": {"href": "https://dev.azure.com/acme/Shop/_workitems/edit/41"}}})
    made = await client.post(f"{API}/audits/{job.id}/issues", headers=auth_headers, json={"source": "security", "index": 0})
    assert made.status_code == 201 and made.json()["issue_key"] == "#41" and made.json()["issue_url"].endswith("/edit/41")
    sent = httpx_mock.get_requests()[-1]
    patch = json.loads(sent.content)
    assert sent.headers["content-type"] == "application/json-patch+json" and sent.headers["authorization"].startswith("Basic ")
    assert patch[0] == {"op": "add", "path": "/fields/System.Title", "value": "[Critical] SQL injection"} and "&lt;q&gt;" in patch[1]["value"]
