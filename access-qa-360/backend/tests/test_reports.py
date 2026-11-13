import uuid

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.project import Project
from app.models.report import Report
from app.models.scan import Scan, ScanStatus
from app.services import report_generator
from tests.conftest import TestSessionLocal


@pytest.fixture
async def scan_id(test_user, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))

    async def no_build(report_id):  # do not call Claude or write files during tests
        return ""

    monkeypatch.setattr(report_generator, "generate_report", no_build)
    async with TestSessionLocal() as db:
        project = Project(id=str(uuid.uuid4()), name="Shop", base_url="https://shop.example.com", owner_id=test_user.id)
        scan = Scan(id=str(uuid.uuid4()), project_id=project.id, url="https://shop.example.com",
                    status=ScanStatus.completed, created_by=test_user.id)
        db.add_all([project, scan])
        await db.commit()
        return scan.id


@pytest.mark.asyncio
async def test_report_goes_from_generating_to_ready_and_downloads(client: AsyncClient, auth_headers, scan_id, tmp_path):
    # "executive" is the name the web app sends; it is stored as executive_summary.
    r = await client.post(f"/api/v1/scans/{scan_id}/reports", headers=auth_headers,
                          json={"report_type": "executive", "format": "pdf"})
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["report_type"] == "executive_summary"
    assert report["status"] == "generating" and report["download_url"] is None
    assert (await client.get(f"/api/v1/reports/{report['id']}/download", headers=auth_headers)).status_code == 404

    built = tmp_path / "built.pdf"
    built.write_bytes(b"%PDF-1.4 done")
    async with TestSessionLocal() as db:
        row = await db.get(Report, report["id"])
        row.file_path = str(built)
        await db.commit()

    listed = (await client.get(f"/api/v1/scans/{scan_id}/reports", headers=auth_headers)).json()
    assert listed[0]["status"] == "ready"
    assert listed[0]["download_url"] == f"/reports/{report['id']}/download"

    r = await client.get(f"/api/v1{listed[0]['download_url']}", headers=auth_headers)
    assert r.status_code == 200 and r.content == b"%PDF-1.4 done"
    assert "wiseflow-executive-summary" in r.headers["content-disposition"]


@pytest.mark.asyncio
async def test_report_rejects_formats_that_are_not_built(client: AsyncClient, auth_headers, scan_id):
    for body in ({"report_type": "vulnerability", "format": "docx"}, {"report_type": "nonsense", "format": "pdf"}):
        r = await client.post(f"/api/v1/scans/{scan_id}/reports", headers=auth_headers, json=body)
        assert r.status_code == 422
