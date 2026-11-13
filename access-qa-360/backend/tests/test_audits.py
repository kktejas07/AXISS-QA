import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.api.routes import audits as audits_routes
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.audit_job import AuditJob, AuditStatus
from app.models.user import User
from app.services import audit_orchestrator
from app.services.web_auditor import PageAuditResult
from tests.conftest import TestSessionLocal


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    """Uploads and reports go to a throwaway folder."""
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def launched(monkeypatch):
    """Record which jobs were started instead of running a real crawl."""
    started: list[str] = []
    monkeypatch.setattr(audits_routes, "_launch", started.append)
    return started


async def _draft(client: AsyncClient, headers, **body) -> dict:
    r = await client.post("/api/v1/audits", headers=headers, json={"autostart": False, **body})
    assert r.status_code == 201, r.text
    return r.json()


START = {"outputs": ["security", "manual"], "depth": "quick", "ownership_confirmed": True}


@pytest.mark.asyncio
async def test_web_scan_is_a_draft_until_started(client: AsyncClient, auth_headers, launched):
    job = await _draft(client, auth_headers, target_url="https://shop.example.com")
    assert job["started_at"] is None and launched == []
    assert job["allowed_outputs"] == ["security", "manual", "playwright"]
    assert job["exports"] == []

    r = await client.post(f"/api/v1/audits/{job['id']}/start", headers=auth_headers, json=START)
    assert r.status_code == 200, r.text
    started = r.json()
    assert started["outputs"] == ["security", "manual"] and started["depth"] == "quick"
    assert started["started_at"] is not None
    assert launched == [job["id"]]

    again = await client.post(f"/api/v1/audits/{job['id']}/start", headers=auth_headers, json=START)
    assert again.status_code == 409 and launched == [job["id"]]


@pytest.mark.asyncio
async def test_start_needs_permission_and_valid_outputs(client: AsyncClient, auth_headers, launched):
    job = await _draft(client, auth_headers, target_url="https://shop.example.com")
    url = f"/api/v1/audits/{job['id']}/start"

    r = await client.post(url, headers=auth_headers, json={**START, "ownership_confirmed": False})
    assert r.status_code == 400
    r = await client.post(url, headers=auth_headers, json={**START, "outputs": ["appium"]})
    assert r.status_code == 422  # Appium needs a mobile build
    r = await client.post(url, headers=auth_headers, json={**START, "outputs": []})
    assert r.status_code == 422
    assert launched == []


@pytest.mark.asyncio
async def test_web_scan_rejects_a_bad_address(client: AsyncClient, auth_headers, launched):
    for bad in ("shop.example.com", "ftp://shop.example.com", ""):
        r = await client.post("/api/v1/audits", headers=auth_headers, json={"target_url": bad})
        assert r.status_code == 422
    assert launched == []


@pytest.mark.asyncio
async def test_original_one_call_create_still_runs_everything(client: AsyncClient, auth_headers, launched):
    r = await client.post("/api/v1/audits", headers=auth_headers, json={"target_url": "https://shop.example.com"})
    assert r.status_code == 201
    assert r.json()["started_at"] is not None and r.json()["outputs"] is None
    assert launched == [r.json()["id"]]


@pytest.mark.asyncio
async def test_mobile_scan_needs_its_build(client: AsyncClient, auth_headers, launched, storage):
    job = await _draft(client, auth_headers, source_type="android")
    assert job["target_url"] is None
    assert job["allowed_outputs"] == ["security", "manual", "appium"]
    base = f"/api/v1/audits/{job['id']}"
    mobile_start = {**START, "outputs": ["security", "appium"]}

    assert (await client.post(f"{base}/start", headers=auth_headers, json=mobile_start)).status_code == 400

    r = await client.post(f"{base}/upload", headers=auth_headers, files={"file": ("notes.txt", b"hello")})
    assert r.status_code == 415
    r = await client.post(f"{base}/upload", headers=auth_headers, files={"file": ("shop.ipa", b"PK...")})
    assert r.status_code == 415  # an iOS build on an Android scan
    r = await client.post(f"{base}/upload", headers=auth_headers, files={"file": ("empty.apk", b"")})
    assert r.status_code == 400

    r = await client.post(f"{base}/upload", headers=auth_headers, files={"file": ("../shop-2.4.apk", b"PK\x03\x04fake")})
    assert r.status_code == 200, r.text
    assert r.json()["source_filename"] == "shop-2.4.apk" and r.json()["label"] == "shop-2.4.apk"
    assert [f.name for f in (storage / "uploads").iterdir()] == [f"{job['id']}.apk"]

    r = await client.post(f"{base}/start", headers=auth_headers, json=mobile_start)
    assert r.status_code == 200 and launched == [job["id"]]

    r = await client.post(f"{base}/upload", headers=auth_headers, files={"file": ("shop-2.5.apk", b"PK\x03\x04new")})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_upload_size_limit(client: AsyncClient, auth_headers, launched, monkeypatch, storage):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    job = await _draft(client, auth_headers, source_type="android")
    big = b"x" * (1024 * 1024 + 1)
    r = await client.post(f"/api/v1/audits/{job['id']}/upload", headers=auth_headers, files={"file": ("big.apk", big)})
    assert r.status_code == 413
    assert list((storage / "uploads").iterdir()) == []


async def _finished_job(owner_id: str, storage, **extra) -> str:
    pdf = storage / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    async with TestSessionLocal() as db:
        job = AuditJob(
            id=str(uuid.uuid4()),
            created_by=owner_id,
            target_url="https://shop.example.com",
            outputs=["security", "manual", "playwright"],
            status=AuditStatus.completed,
            progress=100,
            started_at=datetime.now(timezone.utc),
            critical_count=1,
            high_count=1,
            total_test_cases=2,
            report_pdf_path=str(pdf),
            tier1_result={"playwright_tests": "def test_home(page):\n    page.goto('/')\n"},
            tier3_result={"findings": [
                {"id": "a1", "severity": "high", "title": "Missing CSRF token", "affected_url": "https://shop.example.com/checkout"},
                {"id": "a2", "severity": "critical", "title": "Login accepts a forged token", "affected_url": "https://shop.example.com/api/login"},
                {"id": "a3", "severity": "low", "title": "Server header shows version", "affected_url": "https://shop.example.com"},
            ]},
            tier4_result={"test_cases": [{"id": "TC-001"}, {"id": "TC-002"}], "jira_csv": "id,title\nTC-001,Sign in\n"},
            **extra,
        )
        db.add(job)
        await db.commit()
        return job.id


@pytest.mark.asyncio
async def test_exports(client: AsyncClient, test_user, auth_headers, storage):
    job_id = await _finished_job(test_user.id, storage)
    base = f"/api/v1/audits/{job_id}"

    detail = (await client.get(base, headers=auth_headers)).json()
    assert detail["exports"] == ["report", "test-cases", "playwright", "results"]

    r = await client.get(f"{base}/export/report", headers=auth_headers)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert "attachment" in r.headers["content-disposition"] and ".pdf" in r.headers["content-disposition"]

    r = await client.get(f"{base}/export/test-cases", headers=auth_headers)
    assert r.status_code == 200 and r.text.startswith("id,title") and ".csv" in r.headers["content-disposition"]

    r = await client.get(f"{base}/export/playwright", headers=auth_headers)
    assert r.status_code == 200 and "def test_home" in r.text

    r = await client.get(f"{base}/export/results", headers=auth_headers)
    assert r.status_code == 200 and r.json()["security"]["findings"][1]["severity"] == "critical"

    assert (await client.get(f"{base}/export/appium", headers=auth_headers)).status_code == 404
    assert (await client.get(f"{base}/export/everything", headers=auth_headers)).status_code == 422
    assert (await client.get(f"{base}/download", headers=auth_headers)).status_code == 200


@pytest.mark.asyncio
async def test_scans_are_private_to_their_owner(client: AsyncClient, test_user, auth_headers, storage):
    job_id = await _finished_job(test_user.id, storage)
    async with TestSessionLocal() as db:
        other = User(id=str(uuid.uuid4()), email="other@example.com", full_name="Other", hashed_password=get_password_hash("x"))
        db.add(other)
        await db.commit()
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id)}"}

    assert (await client.get(f"/api/v1/audits/{job_id}", headers=other_headers)).status_code == 404
    assert (await client.get(f"/api/v1/audits/{job_id}/export/report", headers=other_headers)).status_code == 404
    assert (await client.get("/api/v1/audits", headers=other_headers)).json() == []
    assert len((await client.get("/api/v1/audits", headers=auth_headers)).json()) == 1


@pytest.mark.asyncio
async def test_dashboard_counts_started_scans_only(client: AsyncClient, test_user, auth_headers, launched, storage):
    job_id = await _finished_job(test_user.id, storage)
    await _draft(client, auth_headers, target_url="https://draft.example.com")  # never started

    data = (await client.get("/api/v1/dashboard/summary", headers=auth_headers)).json()
    assert data["scans"] == 1
    assert data["open_vulnerabilities"]["critical"] == 1 and data["open_vulnerabilities"]["high"] == 1
    assert data["test_cases"] == {"manual": 2}
    assert [(s["kind"], s["id"], s["total"]) for s in data["recent_scans"]] == [("audit", job_id, 3)]
    assert [(f["severity"], f["kind"]) for f in data["top_findings"]] == [("critical", "audit"), ("high", "audit")]


@pytest.mark.asyncio
async def test_run_only_produces_what_was_asked_for(test_user, storage, monkeypatch):
    """The runner skips unselected work and writes a real PDF."""
    calls: list[str] = []

    async def fake_crawl(url, *, max_depth, max_pages, **_):
        calls.append(f"crawl depth={max_depth} pages={max_pages}")
        page = PageAuditResult()
        page.url, page.path, page.title = url, "/", "Home"
        return [page]

    async def fake_manual(pages):
        calls.append("manual")
        return [{"id": "TC-001", "title": "Sign in", "steps": ["Open the page"], "expected_result": "Signed in"}]

    async def never(*_, **__):
        raise AssertionError("this step was not selected and must not run")

    async def fake_summary(job):
        return "All good.\n\nNothing urgent."

    monkeypatch.setattr(audit_orchestrator, "AsyncSessionLocal", TestSessionLocal)
    monkeypatch.setattr(audit_orchestrator, "crawl_and_audit", fake_crawl)
    monkeypatch.setattr(audit_orchestrator, "generate_manual_test_cases", fake_manual)
    monkeypatch.setattr(audit_orchestrator, "generate_playwright_tests", never)
    monkeypatch.setattr(audit_orchestrator, "run_api_audit", never)
    monkeypatch.setattr(audit_orchestrator, "run_mobile_audit", never)
    monkeypatch.setattr(audit_orchestrator, "_generate_unified_summary", fake_summary)

    async with TestSessionLocal() as db:
        job = AuditJob(id=str(uuid.uuid4()), created_by=test_user.id, target_url="https://shop.example.com",
                       outputs=["manual"], depth="quick", started_at=datetime.now(timezone.utc))
        db.add(job)
        await db.commit()

    await audit_orchestrator.run_audit(job.id)

    async with TestSessionLocal() as db:
        done = await db.get(AuditJob, job.id)
    assert calls == ["crawl depth=1 pages=10", "manual"]
    assert done.status == AuditStatus.completed and done.progress == 100
    assert (done.tier1_status, done.tier2_status, done.tier3_status, done.tier4_status, done.tier5_status) == (
        "completed", "skipped", "skipped", "completed", "completed")
    assert done.tier1_result["playwright_tests"] == ""
    assert done.total_test_cases == 1
    assert done.exports == ["report", "test-cases", "results"]
    with open(done.report_pdf_path, "rb") as f:
        assert f.read(5) == b"%PDF-"


@pytest.mark.asyncio
async def test_run_fails_cleanly_when_the_app_cannot_be_reached(test_user, storage, monkeypatch):
    async def unreachable(url, **_):
        return []

    monkeypatch.setattr(audit_orchestrator, "AsyncSessionLocal", TestSessionLocal)
    monkeypatch.setattr(audit_orchestrator, "crawl_and_audit", unreachable)

    async with TestSessionLocal() as db:
        job = AuditJob(id=str(uuid.uuid4()), created_by=test_user.id, target_url="https://down.example.com",
                       outputs=["manual"], started_at=datetime.now(timezone.utc))
        db.add(job)
        await db.commit()

    await audit_orchestrator.run_audit(job.id)

    async with TestSessionLocal() as db:
        done = await db.get(AuditJob, job.id)
    assert done.status == AuditStatus.failed and done.tier1_status == "failed"
    assert "Could not load" in done.tier1_result["error"]
    assert done.report_pdf_path is None and done.completed_at is not None


@pytest.mark.asyncio
async def test_report_is_still_written_when_the_ai_summary_fails(test_user, storage, monkeypatch):
    async def one_page(url, **_):
        page = PageAuditResult()
        page.url, page.path = url, "/"
        return [page]

    async def no_ai(job):
        raise RuntimeError("Error code: 401 - invalid x-api-key\nlong provider detail that users should not see")

    monkeypatch.setattr(audit_orchestrator, "AsyncSessionLocal", TestSessionLocal)
    monkeypatch.setattr(audit_orchestrator, "crawl_and_audit", one_page)
    monkeypatch.setattr(audit_orchestrator, "_generate_unified_summary", no_ai)

    async with TestSessionLocal() as db:
        job = AuditJob(id=str(uuid.uuid4()), created_by=test_user.id, target_url="https://shop.example.com",
                       outputs=["playwright"], started_at=datetime.now(timezone.utc))
        monkeypatch.setattr(audit_orchestrator, "generate_playwright_tests", lambda pages, url: _text("def test_home(page): pass"))
        db.add(job)
        await db.commit()

    await audit_orchestrator.run_audit(job.id)

    async with TestSessionLocal() as db:
        done = await db.get(AuditJob, job.id)
    assert done.status == AuditStatus.completed and done.tier5_status == "completed"
    assert done.tier5_result["summary_error"] == "Error code: 401 - invalid x-api-key"
    assert "found 0 security findings: 0 critical and 0 high" in done.executive_summary
    assert "report" in done.exports and "playwright" in done.exports


async def _text(value: str) -> str:
    return value
