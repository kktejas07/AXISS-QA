"""Stopping scans, the admin queue, AI usage and platform health."""
import asyncio
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine, select

from app.core import ai
from app.models.audit_job import AuditJob, AuditStatus
from app.models.integration import AiUsage
from app.models.organization import AdminAuditLog
from app.models.user import ROLE_SUPER_ADMIN, User
from app.services import audit_orchestrator, scan_control
from tests.conftest import TestSessionLocal


@pytest.fixture
async def admin_headers(test_user, auth_headers):
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).role = ROLE_SUPER_ADMIN
        await db.commit()
    return auth_headers


async def _job(test_user, **fields) -> str:
    async with TestSessionLocal() as db:
        me = await db.get(User, test_user.id)
        job = AuditJob(created_by=me.id, organization_id=me.organization_id, target_url="https://shop.example.com",
                       started_at=datetime.now(timezone.utc), **fields)
        db.add(job)
        await db.commit()
        return job.id


async def test_a_running_scan_can_be_stopped(client: AsyncClient, test_user, auth_headers, monkeypatch):
    reached = asyncio.Event()

    async def slow_scan(job_id: str):
        reached.set()
        await asyncio.sleep(60)

    monkeypatch.setattr(audit_orchestrator, "run_audit", slow_scan)
    job_id = await _job(test_user, status=AuditStatus.running, progress=20, tier1_status="completed", tier1_result={"pages_audited": 3}, tier3_status="running")
    scan_control.launch(job_id)
    await reached.wait()
    assert scan_control.is_running_here(job_id)

    r = await client.post(f"/api/v1/audits/{job_id}/stop", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "failed" and r.json()["completed_at"] is not None
    assert not scan_control.is_running_here(job_id)          # the work itself was cancelled
    detail = (await client.get(f"/api/v1/audits/{job_id}", headers=auth_headers)).json()
    assert detail["tier1_status"] == "completed" and detail["tier1_result"] == {"pages_audited": 3}   # finished work is kept
    assert detail["tier3_status"] == "failed" and "Stopped by Test User" in detail["tier3_result"]["error"]
    assert detail["tier5_status"] == "skipped"

    assert (await client.post(f"/api/v1/audits/{job_id}/stop", headers=auth_headers)).status_code == 409


async def test_admin_queue_shows_stale_scans_and_can_clear_them(client: AsyncClient, test_user, admin_headers):
    stale = await _job(test_user, status=AuditStatus.running, progress=40, tier3_status="running")     # no task behind it
    await _job(test_user, status=AuditStatus.failed, progress=100, completed_at=datetime.now(timezone.utc), tier1_status="failed", tier1_result={"error": "Could not load any page at that address"})
    await _job(test_user, status=AuditStatus.completed, progress=100, completed_at=datetime.now(timezone.utc))

    q = (await client.get("/api/v1/admin/queue", headers=admin_headers)).json()
    assert q["completed_last_24h"] == 1
    (active,) = q["active"]
    assert active["id"] == stale and active["alive"] is False and active["step"] == "Security checks" and active["started_by"] == "test@example.com"
    (failed,) = q["failed_last_24h"]
    assert failed["problem"] == "Reading the app: Could not load any page at that address"

    r = await client.post(f"/api/v1/admin/audits/{stale}/stop", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "failed"
    assert (await client.get("/api/v1/admin/queue", headers=admin_headers)).json()["active"] == []
    async with TestSessionLocal() as db:
        assert "scan.stop" in [a.action for a in (await db.execute(select(AdminAuditLog))).scalars().all()]


async def test_ai_calls_are_counted_and_costed(client: AsyncClient, test_user, admin_headers, monkeypatch):
    # Point the recorder at the test database.
    monkeypatch.setattr(ai, "_engine", lambda: create_engine("sqlite:///./test.db"))
    org = (await client.get("/api/v1/auth/me", headers=admin_headers)).json()["organization_id"]
    ai.record_usage("claude-sonnet-4-5", "Scan summary", 1_000_000, 200_000, True, {"organization_id": org, "audit_id": "a1"})
    ai.record_usage("claude-haiku-4-5", "Web tests", 500_000, 100_000, True, {"organization_id": org})
    ai.record_usage("claude-haiku-4-5", "Web tests", 0, 0, False, {})
    ai.record_usage("some-future-model", "Reports", 10, 10, True, {})

    data = (await client.get("/api/v1/admin/ai-usage", headers=admin_headers)).json()
    assert data["total"] == {"calls": 4, "failed": 1, "input_tokens": 1_500_010, "output_tokens": 300_010, "cost": 7.0}
    assert data["by_model"][0] == {"model": "claude-sonnet-4-5", "calls": 1, "failed": 0, "input_tokens": 1_000_000, "output_tokens": 200_000, "cost": 6.0}
    assert {m["model"]: m["cost"] for m in data["by_model"]}["claude-haiku-4-5"] == 1.0
    assert data["unpriced_models"] == ["some-future-model"]
    assert {p["purpose"]: p["calls"] for p in data["by_purpose"]} == {"Scan summary": 1, "Web tests": 2, "Reports": 1}
    assert len(data["by_day"]) == 1 and len(data["by_organization"]) == 2


async def test_a_failed_recording_never_breaks_the_call(monkeypatch):
    def broken():
        raise RuntimeError("database is down")

    monkeypatch.setattr(ai, "_engine", broken)
    ai.record_usage("claude-haiku-4-5", "Web tests", 1, 1, True, {})     # must not raise


async def test_health_reports_each_part(client: AsyncClient, admin_headers, auth_headers, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    data = (await client.get("/api/v1/admin/health", headers=admin_headers)).json()
    checks = {c["name"]: c for c in data["checks"]}
    assert checks["Database"]["status"] == "ok" and checks["File storage"]["status"] == "ok"
    assert checks["Queue (Redis)"]["status"] == "down"          # no Redis in the test environment
    assert checks["Email"]["status"] == "off" and checks["Email"]["required"] is False
    assert checks["AI service key"]["status"] == "off"          # the test key is a placeholder
    assert data["healthy"] is False                              # a required part is down


async def test_ops_pages_are_for_super_admins_only(client: AsyncClient, test_user, auth_headers):
    for path in ("/api/v1/admin/queue", "/api/v1/admin/ai-usage", "/api/v1/admin/health"):
        assert (await client.get(path, headers=auth_headers)).status_code == 403
