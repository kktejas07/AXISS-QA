"""The public site's contact form and status check, and the admin's view of contact requests."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.routes import public
from app.core.config import settings
from app.models.organization import AdminAuditLog
from app.models.platform import ContactRequest
from app.models.user import ROLE_SUPER_ADMIN, User
from tests.conftest import TestSessionLocal

API = "/api/v1"
ASK = {"name": "  Priya   Nair ", "email": "Priya@Example.com", "company": "Northwind", "kind": "pricing", "message": "We are 14 people. What would a Team plan cost?"}


@pytest.fixture(autouse=True)
def fresh():
    public._recent.clear()


@pytest.fixture
async def admin_headers(test_user, auth_headers):
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).role = ROLE_SUPER_ADMIN
        await db.commit()
    return auth_headers


async def test_a_contact_request_is_kept_emailed_and_shown_to_the_super_admin(client: AsyncClient, auth_headers, admin_headers, monkeypatch):
    sent = []

    async def send(to, subject, body):
        sent.append((to, subject, body))
        return True

    monkeypatch.setattr(public, "send_email", send)
    monkeypatch.setattr(settings, "SALES_EMAIL", "sales@wiseflow.example")
    assert (await client.post(f"{API}/public/contact", json=ASK)).json() == {"received": True}          # no sign-in needed
    assert sent[0][0] == "sales@wiseflow.example" and sent[0][1] == "Wiseflow contact: A price for my team (Priya Nair)" and "priya@example.com" in sent[0][2]

    listed = (await client.get(f"{API}/admin/contacts", headers=admin_headers)).json()
    assert [(c["name"], c["email"], c["company"], c["about"], c["handled_at"]) for c in listed] == [("Priya Nair", "priya@example.com", "Northwind", "A price for my team", None)]
    done = await client.put(f"{API}/admin/contacts/{listed[0]['id']}", headers=admin_headers, json={"handled": True})
    assert done.json()["handled_at"] is not None
    assert (await client.put(f"{API}/admin/contacts/nope", headers=admin_headers, json={"handled": True})).status_code == 404
    async with TestSessionLocal() as db:
        assert [(e.action, e.target) for e in (await db.execute(select(AdminAuditLog))).scalars().all()] == [("contact.handled", "priya@example.com")]


async def test_only_a_super_admin_reads_contact_requests(client: AsyncClient, auth_headers):
    assert (await client.get(f"{API}/admin/contacts", headers=auth_headers)).status_code == 403
    assert (await client.get(f"{API}/admin/contacts")).status_code in (401, 403)


async def test_bad_and_scripted_messages_are_not_kept(client: AsyncClient):
    for change in ({"email": "not-an-address"}, {"message": "hi"}, {"name": ""}, {"kind": "spam"}):
        assert (await client.post(f"{API}/public/contact", json={**ASK, **change})).status_code == 422, change
    # The hidden field is filled in: thanked, and nothing stored.
    assert (await client.post(f"{API}/public/contact", json={**ASK, "website": "http://spam.example"})).status_code == 201
    async with TestSessionLocal() as db:
        assert (await db.execute(select(ContactRequest))).scalars().all() == []


async def test_one_sender_is_limited_to_a_few_messages_an_hour(client: AsyncClient):
    for _ in range(public.PER_HOUR):
        assert (await client.post(f"{API}/public/contact", json=ASK)).status_code == 201
    over = await client.post(f"{API}/public/contact", json=ASK)
    assert over.status_code == 429 and "Try again later" in over.json()["detail"]


async def test_status_says_whether_the_service_is_up(client: AsyncClient):
    r = (await client.get(f"{API}/status")).json()
    assert r["ok"] is True and [p["name"] for p in r["parts"]] == ["Website and API", "Database"]
