"""Forgotten passwords, changing a password, and admin-made reset links."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.models.organization import AdminAuditLog, PasswordReset
from app.models.user import ROLE_SUPER_ADMIN, User
from app.services import mailer
from tests.conftest import TestSessionLocal

API = "/api/v1/auth"


@pytest.fixture
def outbox(monkeypatch):
    """Turn email on and collect what would be sent."""
    sent: list[dict] = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "no-reply@example.com")
    monkeypatch.setattr(settings, "APP_URL", "https://app.example.com/")
    monkeypatch.setattr(mailer, "_send", lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}))
    return sent


def _token(message: dict) -> str:
    return message["body"].split("reset-password?token=")[1].split()[0]


async def _login(client: AsyncClient, password: str) -> int:
    return (await client.post(f"{API}/login", json={"email": "test@example.com", "password": password})).status_code


async def test_forgot_password_emails_a_single_use_link(client: AsyncClient, test_user, auth_headers, outbox):
    r = await client.post(f"{API}/forgot-password", json={"email": "Test@Example.com"})
    assert r.status_code == 200 and r.json() == {"delivery": "email"}
    (message,) = outbox
    assert message["to"] == "test@example.com" and "https://app.example.com/reset-password?token=" in message["body"]
    token = _token(message)

    # Only a hash is kept, so a database leak does not hand out working links.
    async with TestSessionLocal() as db:
        (row,) = (await db.execute(select(PasswordReset))).scalars().all()
    assert token not in (row.token_hash, row.id) and len(row.token_hash) == 64

    assert (await client.get(f"{API}/reset-password/{token}")).json() == {"email": "test@example.com"}
    short = await client.post(f"{API}/reset-password", json={"token": token, "password": "short"})
    assert short.status_code == 422
    done = await client.post(f"{API}/reset-password", json={"token": token, "password": "a-new-password-1"})
    assert done.status_code == 200

    assert await _login(client, "testpass123") == 401
    assert await _login(client, "a-new-password-1") == 200
    # The session from before the reset is signed out.
    assert (await client.get(f"{API}/me", headers=auth_headers)).status_code == 401
    # The link works once.
    assert (await client.get(f"{API}/reset-password/{token}")).status_code == 404
    again = await client.post(f"{API}/reset-password", json={"token": token, "password": "another-password-2"})
    assert again.status_code == 400 and await _login(client, "a-new-password-1") == 200


async def test_forgot_password_does_not_reveal_who_has_an_account(client: AsyncClient, test_user, outbox):
    r = await client.post(f"{API}/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200 and r.json() == {"delivery": "email"} and outbox == []


async def test_forgot_password_is_limited_per_hour(client: AsyncClient, test_user, outbox):
    for _ in range(5):
        assert (await client.post(f"{API}/forgot-password", json={"email": "test@example.com"})).status_code == 200
    assert len(outbox) == 3


async def test_forgot_password_says_when_the_server_sends_no_email(client: AsyncClient, test_user):
    r = await client.post(f"{API}/forgot-password", json={"email": "test@example.com"})
    assert r.json() == {"delivery": "admin"}
    async with TestSessionLocal() as db:
        assert (await db.execute(select(PasswordReset))).scalars().all() == []


async def test_expired_and_unknown_links_are_refused(client: AsyncClient, test_user, outbox, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_MINUTES", -1)
    await client.post(f"{API}/forgot-password", json={"email": "test@example.com"})
    token = _token(outbox[0])
    assert (await client.get(f"{API}/reset-password/{token}")).status_code == 404
    assert (await client.post(f"{API}/reset-password", json={"token": token, "password": "a-new-password-1"})).status_code == 400
    assert (await client.post(f"{API}/reset-password", json={"token": "made-up", "password": "a-new-password-1"})).status_code == 400
    assert await _login(client, "testpass123") == 200


async def test_change_password_needs_the_current_one_and_signs_out_other_devices(client: AsyncClient, test_user, auth_headers):
    wrong = await client.post(f"{API}/change-password", headers=auth_headers, json={"current_password": "nope", "new_password": "a-new-password-1"})
    assert wrong.status_code == 400
    same = await client.post(f"{API}/change-password", headers=auth_headers, json={"current_password": "testpass123", "new_password": "testpass123"})
    assert same.status_code == 400
    ok = await client.post(f"{API}/change-password", headers=auth_headers, json={"current_password": "testpass123", "new_password": "a-new-password-1"})
    assert ok.status_code == 200
    fresh = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    assert (await client.get(f"{API}/me", headers=fresh)).status_code == 200      # this device stays signed in
    assert (await client.get(f"{API}/me", headers=auth_headers)).status_code == 401  # the old session does not
    assert await _login(client, "a-new-password-1") == 200


async def test_super_admin_can_make_a_reset_link(client: AsyncClient, test_user, auth_headers):
    url = f"/api/v1/admin/users/{test_user.id}/reset-link"
    assert (await client.post(url, headers=auth_headers)).status_code == 403    # ordinary users cannot

    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).role = ROLE_SUPER_ADMIN
        await db.commit()
    r = await client.post(url, headers=auth_headers)
    assert r.status_code == 200, r.text
    link = r.json()["url"]
    assert link.startswith(settings.APP_URL.rstrip("/") + "/reset-password?token=") and r.json()["email"] == "test@example.com"
    token = link.split("token=")[1]
    assert (await client.post(f"{API}/reset-password", json={"token": token, "password": "a-new-password-1"})).status_code == 200
    assert await _login(client, "a-new-password-1") == 200
    async with TestSessionLocal() as db:
        actions = [(a.action, a.target) for a in (await db.execute(select(AdminAuditLog))).scalars().all()]
    assert ("user.reset_link", "test@example.com") in actions
    assert (await client.post("/api/v1/admin/users/missing/reset-link", headers={"Authorization": f"Bearer {(await client.post(f'{API}/login', json={'email': 'test@example.com', 'password': 'a-new-password-1'})).json()['access_token']}"})).status_code == 404


async def test_invites_are_emailed_when_email_is_set_up(client: AsyncClient, test_user, auth_headers, outbox):
    async with TestSessionLocal() as db:
        from app.models.organization import Organization
        me = await db.get(User, test_user.id)
        org = await db.get(Organization, me.organization_id) if me.organization_id else None
        if org is None:
            org = Organization(name="Acme", account_type="team", seat_limit=5)
            db.add(org)
            await db.flush()
            me.organization_id, me.org_role = org.id, "owner"
        org.account_type, org.seat_limit = "team", 5
        await db.commit()
    r = await client.post("/api/v1/org/invites", headers=auth_headers, json={"email": "new@example.com", "role": "viewer"})
    assert r.status_code == 201, r.text
    assert r.json()["emailed"] is True
    (message,) = outbox
    assert message["to"] == "new@example.com" and f"/register?invite={r.json()['token']}" in message["body"]
