import uuid

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.project import Project
from app.models.scan import Scan, ScanStatus
from app.models.user import ROLE_SUPER_ADMIN, User
from app.models.vulnerability import Severity, Vulnerability
from tests.conftest import TestSessionLocal


@pytest.fixture
async def admin_user():
    async with TestSessionLocal() as db:
        user = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            full_name="Admin User",
            hashed_password=get_password_hash("adminpass123"),
            role=ROLE_SUPER_ADMIN,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest.fixture
def admin_headers(admin_user):
    return {"Authorization": f"Bearer {create_access_token(admin_user.id)}"}


async def _seed_scan(owner_id: str, status: ScanStatus = ScanStatus.completed) -> str:
    async with TestSessionLocal() as db:
        project = Project(id=str(uuid.uuid4()), name="Shop", base_url="https://shop.example.com", owner_id=owner_id)
        scan = Scan(
            id=str(uuid.uuid4()),
            project_id=project.id,
            url="https://shop.example.com",
            status=status,
            created_by=owner_id,
        )
        db.add_all([project, scan])
        db.add_all([
            Vulnerability(scan_id=scan.id, severity=Severity.high, title="Missing CSRF token",
                          description="d", affected_url="https://shop.example.com/checkout"),
            Vulnerability(scan_id=scan.id, severity=Severity.critical, title="SQL injection",
                          description="d", affected_url="https://shop.example.com/api/users"),
        ])
        await db.commit()
        return scan.id


@pytest.mark.asyncio
async def test_me_includes_role(client: AsyncClient, auth_headers, admin_headers):
    assert (await client.get("/api/v1/auth/me", headers=auth_headers)).json()["role"] == "user"
    assert (await client.get("/api/v1/auth/me", headers=admin_headers)).json()["role"] == "super_admin"


@pytest.mark.asyncio
async def test_admin_routes_reject_ordinary_users(client: AsyncClient, auth_headers):
    for path in ("/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/scans"):
        assert (await client.get(path, headers=auth_headers)).status_code == 403


@pytest.mark.asyncio
async def test_admin_overview_counts_every_users_data(client: AsyncClient, test_user, admin_headers):
    await _seed_scan(test_user.id)
    await _seed_scan(test_user.id, ScanStatus.queued)
    data = (await client.get("/api/v1/admin/overview", headers=admin_headers)).json()
    assert data["users_total"] == 2
    assert data["super_admins"] == 1
    assert data["projects_total"] == 2
    assert data["scans_total"] == 2
    assert data["scans_queued"] == 1
    assert data["open_vulnerabilities"]["critical"] == 2
    assert data["open_vulnerabilities"]["high"] == 2


@pytest.mark.asyncio
async def test_admin_lists_users_with_counts(client: AsyncClient, test_user, admin_headers):
    await _seed_scan(test_user.id)
    users = (await client.get("/api/v1/admin/users", headers=admin_headers)).json()
    by_email = {u["email"]: u for u in users}
    assert by_email["test@example.com"]["scan_count"] == 1
    assert by_email["test@example.com"]["project_count"] == 1
    assert by_email["admin@example.com"]["scan_count"] == 0


@pytest.mark.asyncio
async def test_admin_can_promote_and_deactivate_a_user(client: AsyncClient, test_user, auth_headers, admin_headers):
    r = await client.patch(f"/api/v1/admin/users/{test_user.id}", headers=admin_headers, json={"role": "super_admin"})
    assert r.status_code == 200 and r.json()["role"] == "super_admin"
    assert (await client.get("/api/v1/admin/overview", headers=auth_headers)).status_code == 200

    r = await client.patch(f"/api/v1/admin/users/{test_user.id}", headers=admin_headers, json={"is_active": False})
    assert r.json()["is_active"] is False
    assert (await client.get("/api/v1/auth/me", headers=auth_headers)).status_code == 401
    login = await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    assert login.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_lock_themselves_out(client: AsyncClient, admin_user, admin_headers):
    r = await client.patch(f"/api/v1/admin/users/{admin_user.id}", headers=admin_headers, json={"role": "user"})
    assert r.status_code == 400
    r = await client.patch(f"/api/v1/admin/users/{admin_user.id}", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_admin_scans_show_owner(client: AsyncClient, test_user, admin_headers):
    await _seed_scan(test_user.id)
    scans = (await client.get("/api/v1/admin/scans", headers=admin_headers)).json()
    assert len(scans) == 1 and scans[0]["owner_email"] == "test@example.com"


@pytest.mark.asyncio
async def test_listed_email_becomes_super_admin(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "SUPER_ADMIN_EMAILS", "boss@example.com, other@example.com")
    r = await client.post("/api/v1/auth/register", json={
        "email": "Boss@example.com", "password": "securepass123", "full_name": "Boss",
    })
    assert r.json()["role"] == "super_admin"
    r = await client.post("/api/v1/auth/register", json={
        "email": "staff@example.com", "password": "securepass123", "full_name": "Staff",
    })
    assert r.json()["role"] == "user"


@pytest.mark.asyncio
async def test_dashboard_summary_is_scoped_to_the_user(client: AsyncClient, test_user, admin_user, auth_headers, admin_headers):
    scan_id = await _seed_scan(test_user.id)
    mine = (await client.get("/api/v1/dashboard/summary", headers=auth_headers)).json()
    assert mine["scans"] == 1 and mine["projects"] == 1
    assert mine["open_vulnerabilities"]["critical"] == 1
    assert mine["recent_scans"][0]["id"] == scan_id
    assert mine["recent_scans"][0]["total"] == 2
    assert [f["severity"] for f in mine["top_findings"]] == ["critical", "high"]

    theirs = (await client.get("/api/v1/dashboard/summary", headers=admin_headers)).json()
    assert theirs["scans"] == 0 and theirs["recent_scans"] == [] and theirs["top_findings"] == []
