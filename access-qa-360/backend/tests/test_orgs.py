import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.routes import audits as audits_routes
from app.core.security import create_access_token, get_password_hash
from app.models.audit_job import AuditJob
from app.models.organization import Organization
from app.models.user import ROLE_SUPER_ADMIN, User
from tests.conftest import TestSessionLocal

API = "/api/v1"


@pytest.fixture(autouse=True)
def no_real_scans(monkeypatch):
    started: list[str] = []
    monkeypatch.setattr(audits_routes, "_launch", started.append)
    return started


async def signup(client: AsyncClient, email: str, name: str = "Person", invite: str | None = None) -> dict:
    """Register and return auth headers plus the created user."""
    body = {"email": email, "password": "password-123", "full_name": name}
    if invite:
        body["invite_token"] = invite
    r = await client.post(f"{API}/auth/register", json=body)
    assert r.status_code == 201, r.text
    login = await client.post(f"{API}/auth/login", json={"email": email, "password": "password-123"})
    return {"headers": {"Authorization": f"Bearer {login.json()['access_token']}"}, "user": r.json()}


@pytest.fixture
async def super_admin():
    async with TestSessionLocal() as db:
        user = User(id=str(uuid.uuid4()), email="root@example.com", full_name="Root", hashed_password=get_password_hash("x"), role=ROLE_SUPER_ADMIN)
        db.add(user)
        await db.commit()
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


async def make_team(client: AsyncClient, super_admin, owner_email="owner@acme.example", seats: int | None = None) -> dict:
    """An owner whose organisation has been moved to a Team account."""
    owner = await signup(client, owner_email, "Olive Owner")
    body = {"account_type": "team"} | ({"seat_limit": seats} if seats else {})
    r = await client.patch(f"{API}/admin/organizations/{owner['user']['organization_id']}", headers=super_admin, json=body)
    assert r.status_code == 200, r.text
    return owner


async def invite_and_join(client: AsyncClient, owner: dict, email: str, role: str) -> dict:
    r = await client.post(f"{API}/org/invites", headers=owner["headers"], json={"email": email, "role": role})
    assert r.status_code == 201, r.text
    return await signup(client, email, email.split("@")[0], invite=r.json()["token"])


@pytest.mark.asyncio
async def test_signup_creates_a_personal_organisation(client: AsyncClient):
    a = await signup(client, "solo@example.com", "Sam Solo")
    assert a["user"]["org_role"] == "owner" and a["user"]["organization_id"]

    me = (await client.get(f"{API}/auth/me", headers=a["headers"])).json()
    assert me["organization"]["name"] == "Sam Solo's workspace"
    assert me["organization"]["account_type"] == "individual"
    assert me["permissions"] == ["members.manage", "org.edit", "scan.run"]

    org = (await client.get(f"{API}/org", headers=a["headers"])).json()
    assert (org["seats_used"], org["seat_limit"], org["my_role"]) == (1, 1, "owner")


@pytest.mark.asyncio
async def test_individual_accounts_cannot_invite(client: AsyncClient):
    a = await signup(client, "solo@example.com")
    r = await client.post(f"{API}/org/invites", headers=a["headers"], json={"email": "friend@example.com"})
    assert r.status_code == 403 and "Team" in r.json()["detail"]


@pytest.mark.asyncio
async def test_invite_link_joins_the_organisation_with_the_given_role(client: AsyncClient, super_admin):
    owner = await make_team(client, super_admin)
    r = await client.post(f"{API}/org/invites", headers=owner["headers"], json={"email": "Vera@Acme.example", "role": "viewer"})
    assert r.status_code == 201
    token = r.json()["token"]

    preview = (await client.get(f"{API}/invites/{token}")).json()
    assert preview == {"organization_name": "Olive Owner's workspace", "email": "vera@acme.example", "role": "viewer"}

    # The link only works for the invited email.
    wrong = await client.post(f"{API}/auth/register", json={"email": "other@acme.example", "password": "password-123", "full_name": "X", "invite_token": token})
    assert wrong.status_code == 400

    vera = await signup(client, "vera@acme.example", "Vera", invite=token)
    assert vera["user"]["organization_id"] == owner["user"]["organization_id"]
    assert vera["user"]["org_role"] == "viewer"

    # A link works once.
    assert (await client.get(f"{API}/invites/{token}")).status_code == 404
    assert (await client.get(f"{API}/org/invites", headers=owner["headers"])).json() == []
    members = (await client.get(f"{API}/org/members", headers=vera["headers"])).json()
    assert [(m["email"], m["org_role"]) for m in members] == [("owner@acme.example", "owner"), ("vera@acme.example", "viewer")]


@pytest.mark.asyncio
async def test_seat_limit_counts_pending_invites(client: AsyncClient, super_admin):
    owner = await make_team(client, super_admin, seats=2)
    first = await client.post(f"{API}/org/invites", headers=owner["headers"], json={"email": "a@acme.example"})
    assert first.status_code == 201
    second = await client.post(f"{API}/org/invites", headers=owner["headers"], json={"email": "b@acme.example"})
    assert second.status_code == 403 and "2 seats" in second.json()["detail"]
    again = await client.post(f"{API}/org/invites", headers=owner["headers"], json={"email": "a@acme.example"})
    assert again.status_code in (403, 409)

    cancel = await client.delete(f"{API}/org/invites/{first.json()['id']}", headers=owner["headers"])
    assert cancel.status_code == 204
    assert (await client.post(f"{API}/org/invites", headers=owner["headers"], json={"email": "b@acme.example"})).status_code == 201


@pytest.mark.asyncio
async def test_roles_decide_who_can_scan_and_everyone_sees_results(client: AsyncClient, super_admin, no_real_scans):
    owner = await make_team(client, super_admin)
    member = await invite_and_join(client, owner, "mia@acme.example", "member")
    viewer = await invite_and_join(client, owner, "vic@acme.example", "viewer")
    outsider = await signup(client, "stranger@elsewhere.example")
    draft = {"target_url": "https://shop.example.com", "autostart": False}

    denied = await client.post(f"{API}/audits", headers=viewer["headers"], json=draft)
    assert denied.status_code == 403 and "Viewer" in denied.json()["detail"]

    created = await client.post(f"{API}/audits", headers=member["headers"], json=draft)
    assert created.status_code == 201
    job_id = created.json()["id"]
    start = {"outputs": ["security"], "depth": "quick", "ownership_confirmed": True}

    assert (await client.post(f"{API}/audits/{job_id}/start", headers=viewer["headers"], json=start)).status_code == 403
    # A colleague can start a scan someone else drafted.
    assert (await client.post(f"{API}/audits/{job_id}/start", headers=owner["headers"], json=start)).status_code == 200
    assert no_real_scans == [job_id]

    for person in (owner, member, viewer):
        assert (await client.get(f"{API}/audits/{job_id}", headers=person["headers"])).status_code == 200
        assert [j["id"] for j in (await client.get(f"{API}/audits", headers=person["headers"])).json()] == [job_id]
        assert (await client.get(f"{API}/dashboard/summary", headers=person["headers"])).json()["scans"] == 1
    assert (await client.get(f"{API}/audits/{job_id}", headers=outsider["headers"])).status_code == 404
    assert (await client.get(f"{API}/audits", headers=outsider["headers"])).json() == []

    viewer_perms = (await client.get(f"{API}/auth/me", headers=viewer["headers"])).json()["permissions"]
    assert viewer_perms == []


@pytest.mark.asyncio
async def test_team_management_rules(client: AsyncClient, super_admin):
    owner = await make_team(client, super_admin)
    admin = await invite_and_join(client, owner, "ada@acme.example", "admin")
    member = await invite_and_join(client, owner, "mia@acme.example", "member")
    owner_id, admin_id, member_id = owner["user"]["id"], admin["user"]["id"], member["user"]["id"]
    members_url = f"{API}/org/members"

    # Members cannot manage the team.
    assert (await client.patch(f"{members_url}/{admin_id}", headers=member["headers"], json={"role": "viewer"})).status_code == 403
    assert (await client.post(f"{API}/org/invites", headers=member["headers"], json={"email": "z@acme.example"})).status_code == 403
    assert (await client.get(f"{API}/org/invites", headers=member["headers"])).status_code == 403

    # Admins manage others, but not the owner, ownership or themselves.
    assert (await client.patch(f"{members_url}/{member_id}", headers=admin["headers"], json={"role": "viewer"})).json()["org_role"] == "viewer"
    assert (await client.patch(f"{members_url}/{owner_id}", headers=admin["headers"], json={"role": "member"})).status_code == 403
    assert (await client.patch(f"{members_url}/{member_id}", headers=admin["headers"], json={"role": "owner"})).status_code == 403
    assert (await client.patch(f"{members_url}/{admin_id}", headers=admin["headers"], json={"role": "member"})).status_code == 400
    assert (await client.delete(f"{members_url}/{owner_id}", headers=admin["headers"])).status_code == 403

    # Handing over ownership leaves exactly one owner.
    r = await client.patch(f"{members_url}/{admin_id}", headers=owner["headers"], json={"role": "owner"})
    assert r.status_code == 200
    roles = {m["email"]: m["org_role"] for m in (await client.get(members_url, headers=owner["headers"])).json()}
    assert roles == {"owner@acme.example": "admin", "ada@acme.example": "owner", "mia@acme.example": "viewer"}

    # A removed person keeps their account but moves to their own empty organisation.
    assert (await client.delete(f"{members_url}/{member_id}", headers=admin["headers"])).status_code == 204
    after = (await client.get(f"{API}/auth/me", headers=member["headers"])).json()
    assert after["organization_id"] != owner["user"]["organization_id"] and after["org_role"] == "owner"
    assert len((await client.get(members_url, headers=owner["headers"])).json()) == 2

    renamed = await client.patch(f"{API}/org", headers=owner["headers"], json={"name": "Acme QA"})
    assert renamed.json()["name"] == "Acme QA"


@pytest.mark.asyncio
async def test_suspension_and_monthly_limit_block_new_scans(client: AsyncClient, super_admin, no_real_scans):
    owner = await signup(client, "owner@acme.example", "Olive Owner")
    org_url = f"{API}/admin/organizations/{owner['user']['organization_id']}"
    start = {"outputs": ["security"], "depth": "quick", "ownership_confirmed": True}

    async def draft() -> str:
        r = await client.post(f"{API}/audits", headers=owner["headers"], json={"target_url": "https://shop.example.com", "autostart": False})
        return r.json()["id"]

    assert (await client.patch(org_url, headers=super_admin, json={"scan_limit": 1})).status_code == 200
    first, second = await draft(), await draft()
    assert (await client.post(f"{API}/audits/{first}/start", headers=owner["headers"], json=start)).status_code == 200
    blocked = await client.post(f"{API}/audits/{second}/start", headers=owner["headers"], json=start)
    assert blocked.status_code == 403 and "all 1 scans" in blocked.json()["detail"]

    assert (await client.patch(org_url, headers=super_admin, json={"scan_limit": None, "status": "suspended"})).status_code == 200
    suspended = await client.post(f"{API}/audits/{second}/start", headers=owner["headers"], json=start)
    assert suspended.status_code == 403 and "suspended" in suspended.json()["detail"]
    assert (await client.get(f"{API}/audits/{first}", headers=owner["headers"])).status_code == 200  # still readable

    assert (await client.patch(org_url, headers=super_admin, json={"status": "active"})).status_code == 200
    assert (await client.post(f"{API}/audits/{second}/start", headers=owner["headers"], json=start)).status_code == 200
    assert no_real_scans == [first, second]


@pytest.mark.asyncio
async def test_admin_manages_organisations_and_every_change_is_logged(client: AsyncClient, super_admin):
    owner = await make_team(client, super_admin)
    await invite_and_join(client, owner, "mia@acme.example", "member")
    org_id = owner["user"]["organization_id"]
    org_url = f"{API}/admin/organizations/{org_id}"

    assert (await client.get(f"{API}/admin/organizations", headers=owner["headers"])).status_code == 403

    listed = (await client.get(f"{API}/admin/organizations", headers=super_admin)).json()
    acme = next(o for o in listed if o["id"] == org_id)
    assert (acme["account_type"], acme["seat_limit"], acme["member_count"], acme["owner_email"]) == ("team", 10, 2, "owner@acme.example")

    detail = (await client.get(org_url, headers=super_admin)).json()
    assert [m["org_role"] for m in detail["members"]] == ["owner", "member"]

    assert (await client.patch(org_url, headers=super_admin, json={"seat_limit": 1})).status_code == 400  # fewer than members
    assert (await client.patch(org_url, headers=super_admin, json={"account_type": "individual"})).status_code == 400
    assert (await client.patch(org_url, headers=super_admin, json={"seat_limit": 0})).status_code == 422
    enterprise = (await client.patch(org_url, headers=super_admin, json={"account_type": "enterprise"})).json()
    assert enterprise["seat_limit"] is None

    await client.patch(f"{API}/admin/users/{owner['user']['id']}", headers=super_admin, json={"is_active": False})

    log = (await client.get(f"{API}/admin/audit-log", headers=super_admin)).json()
    assert {(e["action"], e["detail"]) for e in log} == {
        ("org.account_type", "individual to team"),
        ("org.account_type", "team to enterprise"),
        ("user.deactivate", ""),
    }
    assert all(e["actor_email"] == "root@example.com" for e in log)

    users = (await client.get(f"{API}/admin/users", headers=super_admin)).json()
    mia = next(u for u in users if u["email"] == "mia@acme.example")
    assert (mia["organization_name"], mia["org_role"]) == ("Olive Owner's workspace", "member")


@pytest.mark.asyncio
async def test_accounts_from_before_organisations_get_one_on_first_use(client: AsyncClient, test_user, auth_headers):
    """test_user is created with no organisation, like a user row that predates this feature."""
    async with TestSessionLocal() as db:
        db.add(AuditJob(id="legacy-job", created_by=test_user.id, target_url="https://old.example.com", started_at=datetime.now(timezone.utc)))
        await db.commit()

    me = (await client.get(f"{API}/auth/me", headers=auth_headers)).json()
    assert me["org_role"] == "owner" and me["organization"]["account_type"] == "individual"
    async with TestSessionLocal() as db:
        assert (await db.get(Organization, me["organization_id"])).name == "Test User's workspace"
    # Their older scan, which has no organisation, is still theirs.
    assert [j["id"] for j in (await client.get(f"{API}/audits", headers=auth_headers)).json()] == ["legacy-job"]
