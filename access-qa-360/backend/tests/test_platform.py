"""Platform keys in the admin console, the default AI provider, key health and the monthly AI allowance."""
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine, select

from app.core import ai, platform, providers
from app.core.config import settings
from app.core.secrets import encrypt
from app.models.integration import AiUsage
from app.models.organization import AdminAuditLog, Organization
from app.models.platform import PlatformSetting
from app.models.user import ROLE_SUPER_ADMIN, User
from tests.conftest import TestSessionLocal

API = "/api/v1"
KEY = "sk_live_a_secret_that_must_never_come_back_9f3c"


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    monkeypatch.setattr(ai, "_engine", lambda: create_engine("sqlite:///./test.db"))
    yield
    platform.reset()


@pytest.fixture
async def admin_headers(test_user, auth_headers):
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).role = ROLE_SUPER_ADMIN
        await db.commit()
    return auth_headers


def group(page: dict, name: str) -> dict:
    return next(g for g in page["groups"] if g["id"] == name)


def field(page: dict, name: str, key: str) -> dict:
    return next(f for f in group(page, name)["fields"] if f["key"] == key)


async def test_only_a_super_admin_sees_platform_keys(client: AsyncClient, auth_headers):
    assert (await client.get(f"{API}/admin/platform", headers=auth_headers)).status_code == 403
    assert (await client.put(f"{API}/admin/platform", headers=auth_headers, json={"values": {"STRIPE_SECRET_KEY": KEY}})).status_code == 403


async def test_a_key_goes_in_takes_effect_and_never_comes_back_out(client: AsyncClient, admin_headers):
    before = settings.STRIPE_SECRET_KEY
    page = (await client.get(f"{API}/admin/platform", headers=admin_headers)).json()
    assert group(page, "stripe")["configured"] is False and field(page, "stripe", "STRIPE_SECRET_KEY")["set"] is False

    saved = await client.put(f"{API}/admin/platform", headers=admin_headers, json={"values": {"STRIPE_SECRET_KEY": f"  {KEY} "}})
    assert saved.status_code == 200 and KEY not in saved.text
    shown = field(saved.json(), "stripe", "STRIPE_SECRET_KEY")
    assert shown == {"key": "STRIPE_SECRET_KEY", "label": "Secret key", "secret": True, "set": True, "source": "console", "hint": "ends in 9f3c"}
    assert settings.STRIPE_SECRET_KEY == KEY and group(saved.json(), "stripe")["configured"] is True
    assert KEY not in (await client.get(f"{API}/admin/platform", headers=admin_headers)).text

    async with TestSessionLocal() as db:
        stored = (await db.get(PlatformSetting, "STRIPE_SECRET_KEY")).value_encrypted
        log = (await db.execute(select(AdminAuditLog))).scalars().all()
    assert KEY not in stored
    assert [(e.action, e.target, e.detail) for e in log] == [("platform.setting", "Secret key", "set")]

    gone = await client.put(f"{API}/admin/platform", headers=admin_headers, json={"values": {"STRIPE_SECRET_KEY": ""}})
    assert field(gone.json(), "stripe", "STRIPE_SECRET_KEY")["set"] is False and settings.STRIPE_SECRET_KEY == before


async def test_values_that_cannot_work_are_refused(client: AsyncClient, admin_headers):
    put = lambda **values: client.put(f"{API}/admin/platform", headers=admin_headers, json={"values": values})
    for values, said in [({"DEFAULT_AI_PROVIDER": "skynet"}, "Provider: Choose one of the listed providers"),
                         ({"SMTP_PORT": "smtp"}, "Port: Enter a whole number from 1 to 65535"),
                         ({"EMBEDDINGS_BASE_URL": "http://169.254.169.254/latest"}, "Address: Enter a public address starting with https://"),
                         ({"SECRET_KEY": "mine-now"}, "SECRET_KEY: That setting cannot be changed here"),
                         ({"SMTP_HOST": "mail.example.com\nX-Injected: 1"}, "Mail server: That value is too long or has a line break in it")]:
        r = await put(**values)
        assert r.status_code == 422 and r.json()["detail"] == said, values
    assert (await put(SMTP_PORT="2525", SMTP_HOST="mail.example.com", SMTP_FROM="qa@example.com")).status_code == 200
    assert settings.SMTP_PORT == 2525 and platform.configured("email")


async def test_a_saved_value_is_picked_up_by_another_server_process(client: AsyncClient, admin_headers):
    async with TestSessionLocal() as db:
        db.add(PlatformSetting(key="RAZORPAY_KEY_ID", value_encrypted=encrypt("rzp_live_from_elsewhere")))
        await db.commit()
        await platform.refresh(db)
    assert settings.RAZORPAY_KEY_ID == "rzp_live_from_elsewhere"


async def test_a_key_can_be_tested_and_a_failure_shows_in_system_health(client: AsyncClient, admin_headers, monkeypatch):
    assert (await client.post(f"{API}/admin/platform/stripe/test", headers=admin_headers)).json() == {"ok": False, "detail": "Not set up yet"}
    assert (await client.post(f"{API}/admin/platform/nothing/test", headers=admin_headers)).status_code == 404
    await client.put(f"{API}/admin/platform", headers=admin_headers, json={"values": {"STRIPE_SECRET_KEY": KEY}})
    asked = []

    async def answer(url, **kwargs):
        asked.append((url, kwargs["headers"]["Authorization"]))
        return 401

    monkeypatch.setattr(platform, "_get", answer)
    failed = (await client.post(f"{API}/admin/platform/stripe/test", headers=admin_headers)).json()
    assert failed == {"ok": False, "detail": "Stripe did not accept the key (status 401)"}
    assert asked == [("https://api.stripe.com/v1/balance", f"Bearer {KEY}")]
    health = (await client.get(f"{API}/admin/health", headers=admin_headers)).json()
    stripe = next(c for c in health["checks"] if c["name"] == "Stripe")
    assert stripe["status"] == "down" and "did not accept the key" in stripe["detail"] and stripe["required"] is False

    async def fine(url, **kwargs):
        return 200

    monkeypatch.setattr(platform, "_get", fine)
    assert (await client.post(f"{API}/admin/platform/stripe/test", headers=admin_headers)).json()["ok"] is True
    page = (await client.get(f"{API}/admin/platform", headers=admin_headers)).json()
    assert group(page, "stripe")["last_check"]["ok"] is True
    assert (await client.post(f"{API}/admin/platform/google/test", headers=admin_headers)).json()["ok"] is False        # nothing set up


class FakeClaude:
    """Stands in for the Anthropic client; remembers which key each call was made with."""

    calls: list = []
    error: Exception | None = None

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        FakeClaude.calls.append((self.api_key, kwargs["model"]))
        if FakeClaude.error:
            raise FakeClaude.error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")], usage=SimpleNamespace(input_tokens=1_000_000, output_tokens=0))


@pytest.fixture
def claude(monkeypatch):
    FakeClaude.calls, FakeClaude.error = [], None
    monkeypatch.setattr(ai, "AsyncAnthropic", FakeClaude)
    return FakeClaude


async def ask(context: dict):
    token = ai.ai_context.set(context)
    try:
        return await ai.ai_client("test").messages.create(model="claude-haiku-4-5", max_tokens=5, messages=[{"role": "user", "content": "hi"}])
    finally:
        ai.ai_context.reset(token)


async def test_the_platform_can_use_another_provider_and_model_by_default(client: AsyncClient, admin_headers, claude, monkeypatch):
    sent = []

    async def chat(provider, base, key, model, **kwargs):
        sent.append((provider, key, model))
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")], usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    monkeypatch.setattr(providers, "chat", chat)
    other = "sk-openai-platform-key-0123456789"
    await client.put(f"{API}/admin/platform", headers=admin_headers, json={"values": {"DEFAULT_AI_PROVIDER": "openai", "DEFAULT_AI_KEY": other, "DEFAULT_AI_MODEL": "gpt-4o"}})
    await ask({"organization_id": "org-1"})
    assert sent == [("openai", other, "gpt-4o")] and claude.calls == []
    # An organisation with its own key is not affected by the platform's choice.
    await ask({"organization_id": "org-1", "api_key": "sk-ant-their-own", "provider": "anthropic"})
    assert claude.calls == [("sk-ant-their-own", "claude-haiku-4-5")]
    async with TestSessionLocal() as db:
        rows = (await db.execute(select(AiUsage.model, AiUsage.own_key).order_by(AiUsage.own_key))).all()
    assert rows == [("gpt-4o", False), ("claude-haiku-4-5", True)]


async def test_a_replaced_claude_key_is_used_at_once(client: AsyncClient, admin_headers, claude):
    new = "sk-ant-replaced-from-the-console-0001"
    await client.put(f"{API}/admin/platform", headers=admin_headers, json={"values": {"ANTHROPIC_API_KEY": new}})
    await ask({"organization_id": "org-1"})
    assert claude.calls == [(new, "claude-haiku-4-5")]


async def test_the_monthly_allowance_stops_calls_on_the_platform_key_only(client: AsyncClient, test_user, admin_headers, claude):
    org = (await client.get(f"{API}/auth/me", headers=admin_headers)).json()["organization_id"]
    await ask({"organization_id": org})                                   # one million haiku input tokens: $1
    platform._spend.clear()
    assert platform.month_spend(org) == 1.0

    patch = lambda **body: client.patch(f"{API}/admin/organizations/{org}", headers=admin_headers, json=body)
    assert (await patch(ai_monthly_cap_usd=-1)).status_code == 422
    detail = (await patch(ai_monthly_cap_usd=1)).json()
    assert detail["ai_monthly_cap_usd"] == 1 and detail["ai_spend_this_month"] == 1.0 and detail["ai_own_key"] is False
    with pytest.raises(ai.AiAllowanceUsed):
        await ask({"organization_id": org, "cap": 1})
    await ask({"organization_id": org, "cap": 1, "api_key": "sk-ant-their-own"})      # their own key, their own bill
    await ask({"organization_id": org, "cap": 0})                                      # 0 for this organisation: no limit
    assert len(claude.calls) == 3

    await client.put(f"{API}/admin/platform", headers=admin_headers, json={"values": {"AI_MONTHLY_CAP_USD": "1"}})
    platform._spend.clear()
    with pytest.raises(ai.AiAllowanceUsed):
        await ask({"organization_id": org})                               # no figure of its own: the platform's applies


async def test_a_rejected_platform_key_is_noticed_without_anyone_testing_it(client: AsyncClient, admin_headers, claude):
    refused = Exception("invalid x-api-key")
    refused.status_code = 401
    claude.error = refused
    with pytest.raises(Exception):
        await ask({"organization_id": "org-1"})
    health = (await client.get(f"{API}/admin/health", headers=admin_headers)).json()
    line = next(c for c in health["checks"] if c["name"] == "AI model")
    # In tests the server has no real key, so the line reads "not set up"; the recorded failure is on the keys page.
    page = (await client.get(f"{API}/admin/platform", headers=admin_headers)).json()
    assert group(page, "ai")["last_check"]["ok"] is False and group(page, "ai")["last_check"]["detail"] == "The AI provider did not accept the key"
    assert line["status"] in ("off", "down")


async def test_a_super_admin_can_see_and_remove_an_organisations_own_key(client: AsyncClient, test_user, admin_headers):
    org = (await client.get(f"{API}/auth/me", headers=admin_headers)).json()["organization_id"]
    async with TestSessionLocal() as db:
        row = await db.get(Organization, org)
        row.ai_key_encrypted, row.ai_provider, row.ai_model = encrypt("sk-their-secret-key"), "openai", "gpt-4o"
        await db.commit()
    seen = await client.get(f"{API}/admin/organizations/{org}", headers=admin_headers)
    assert "sk-their-secret-key" not in seen.text
    assert (seen.json()["ai_own_key"], seen.json()["ai_provider"], seen.json()["ai_model"]) == (True, "ChatGPT (OpenAI)", "gpt-4o")
    removed = (await client.delete(f"{API}/admin/organizations/{org}/ai-key", headers=admin_headers)).json()
    assert (removed["ai_own_key"], removed["ai_provider"], removed["ai_model"]) == (False, None, None)
    async with TestSessionLocal() as db:
        assert (await db.get(Organization, org)).ai_key_encrypted is None
        assert [e.action for e in (await db.execute(select(AdminAuditLog))).scalars().all()] == ["org.ai_key_removed"]
