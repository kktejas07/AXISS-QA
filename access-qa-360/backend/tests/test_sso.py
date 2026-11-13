"""Sign in with Google or Microsoft."""
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.models.organization import Invite, Organization
from app.models.user import User
from app.services import sso
from tests.conftest import TestSessionLocal

API = "/api/v1/auth/sso"
TENANT = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def configured(monkeypatch):
    for key, value in (("GOOGLE_CLIENT_ID", "g-id"), ("GOOGLE_CLIENT_SECRET", "g-secret"), ("MICROSOFT_CLIENT_ID", "m-id"),
                       ("MICROSOFT_CLIENT_SECRET", "m-secret"), ("MICROSOFT_TENANT_ID", TENANT), ("APP_URL", "http://app.example.com")):
        monkeypatch.setattr(settings, key, value)


def google(httpx_mock, email="new@acme.io", verified=True, name="New Person"):
    httpx_mock.add_response(url="https://oauth2.googleapis.com/token", method="POST", json={"access_token": "at"})
    httpx_mock.add_response(url="https://openidconnect.googleapis.com/v1/userinfo", json={"email": email, "email_verified": verified, "name": name})


async def _start(client: AsyncClient, provider="google", invite=None) -> str:
    r = await client.get(f"{API}/{provider}/start", params={"invite": invite} if invite else None)
    assert r.status_code == 302
    return parse_qs(urlparse(r.headers["location"]).query)["state"][0]


async def test_providers_are_off_until_configured(client: AsyncClient, monkeypatch):
    assert (await client.get(f"{API}/providers")).json() == {"google": False, "microsoft": False}
    r = await client.get(f"{API}/google/start")
    assert r.status_code == 302 and r.headers["location"].endswith("/login?sso_error=unavailable")
    # Microsoft needs a named tenant; the shared endpoint is refused.
    for key, value in (("MICROSOFT_CLIENT_ID", "m"), ("MICROSOFT_CLIENT_SECRET", "s"), ("MICROSOFT_TENANT_ID", "common")):
        monkeypatch.setattr(settings, key, value)
    assert (await client.get(f"{API}/providers")).json()["microsoft"] is False


async def test_start_sends_the_browser_to_the_provider(client: AsyncClient, configured):
    r = await client.get(f"{API}/google/start")
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "accounts.google.com" and q["client_id"] == ["g-id"] and q["scope"] == ["openid email profile"]
    assert q["redirect_uri"] == ["http://app.example.com/api/v1/auth/sso/google/callback"]
    r = await client.get(f"{API}/microsoft/start")
    assert f"login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize" in r.headers["location"]


async def test_first_google_sign_in_creates_an_account_and_later_ones_reuse_it(client: AsyncClient, configured, httpx_mock):
    state = await _start(client)
    google(httpx_mock, email="New@Acme.io")
    r = await client.get(f"{API}/google/callback", params={"code": "c1", "state": state})
    assert r.status_code == 302 and r.headers["location"].startswith("http://app.example.com/sso#token=")
    token = r.headers["location"].split("#token=")[1]
    me = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).json()
    assert me["email"] == "new@acme.io" and me["full_name"] == "New Person" and me["org_role"] == "owner"

    sent = parse_qs(httpx_mock.get_requests()[0].content.decode())
    assert sent["code"] == ["c1"] and sent["client_secret"] == ["g-secret"] and sent["grant_type"] == ["authorization_code"]

    google(httpx_mock, email="new@acme.io")
    await client.get(f"{API}/google/callback", params={"code": "c2", "state": await _start(client)})
    async with TestSessionLocal() as db:
        assert len((await db.execute(select(User).where(User.email == "new@acme.io"))).scalars().all()) == 1


async def test_an_existing_password_account_can_sign_in_with_google(client: AsyncClient, test_user, configured, httpx_mock):
    google(httpx_mock, email="test@example.com")
    r = await client.get(f"{API}/google/callback", params={"code": "c", "state": await _start(client)})
    token = r.headers["location"].split("#token=")[1]
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).json()["id"] == test_user.id
    assert (await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "testpass123"})).status_code == 200


async def test_sign_in_is_refused_when_it_should_be(client: AsyncClient, test_user, configured, httpx_mock):
    async def outcome(state: str | None = None, **params) -> str:
        """Start a sign-in in this browser (unless a state is given), then come back with these parameters."""
        r = await client.get(f"{API}/google/callback", params={"state": state or await _start(client), **params})
        assert r.status_code == 302
        return r.headers["location"].split("sso_error=")[-1]

    assert await outcome(error="access_denied") == "cancelled"
    assert await outcome(state="forged", code="c") == "expired"
    google_state = await _start(client)
    assert await outcome(state=await _start(client, "microsoft"), code="c") == "expired"      # state from another provider
    assert await outcome(state=google_state, code="c") == "expired"                             # an older attempt in this browser

    # A link started in someone else's browser: the state is genuine but this browser has no matching cookie.
    theirs = await _start(client)
    client.cookies.clear()
    assert await outcome(state=theirs, code="c") == "expired"

    google(httpx_mock, email="someone@acme.io", verified=False)
    assert await outcome(code="c") == "unverified"

    httpx_mock.add_response(url="https://oauth2.googleapis.com/token", method="POST", status_code=400, json={"error": "invalid_grant"})
    assert await outcome(code="used") == "failed"

    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).is_active = False
        await db.commit()
    google(httpx_mock, email="test@example.com")
    assert await outcome(code="c") == "deactivated"
    async with TestSessionLocal() as db:
        assert (await db.execute(select(User).where(User.email == "someone@acme.io"))).scalar_one_or_none() is None


async def test_an_invitation_is_honoured_only_for_its_own_email(client: AsyncClient, test_user, configured, httpx_mock):
    async with TestSessionLocal() as db:
        org = Organization(name="Acme", account_type="team", seat_limit=5)
        db.add(org)
        await db.flush()
        db.add(Invite(organization_id=org.id, email="vera@acme.io", role="viewer", token="invite-token", invited_by=test_user.id))
        await db.commit()
        org_id = org.id

    google(httpx_mock, email="other@acme.io")
    r = await client.get(f"{API}/google/callback", params={"code": "c", "state": await _start(client, invite="invite-token")})
    assert r.headers["location"].endswith("sso_error=invite_mismatch")

    google(httpx_mock, email="vera@acme.io", name="Vera Viewer")
    r = await client.get(f"{API}/google/callback", params={"code": "c", "state": await _start(client, invite="invite-token")})
    token = r.headers["location"].split("#token=")[1]
    me = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).json()
    assert me["organization_id"] == org_id and me["org_role"] == "viewer"


async def test_microsoft_sign_in(client: AsyncClient, configured, httpx_mock):
    httpx_mock.add_response(url=f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token", method="POST", json={"access_token": "at"})
    httpx_mock.add_response(url="https://graph.microsoft.com/oidc/userinfo", json={"email": "sam@contoso.com", "name": "Sam Staff"})
    r = await client.get(f"{API}/microsoft/callback", params={"code": "c", "state": await _start(client, "microsoft")})
    assert "#token=" in r.headers["location"]
    assert sso.redirect_uri("microsoft") == "http://app.example.com/api/v1/auth/sso/microsoft/callback"
