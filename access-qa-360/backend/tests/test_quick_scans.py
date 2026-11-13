"""Quick security scans are saved under one of the user's own projects."""
from httpx import AsyncClient

from app.worker import tasks


async def test_quick_scan_needs_one_of_your_projects(client: AsyncClient, auth_headers, monkeypatch):
    queued: list[str] = []
    monkeypatch.setattr(tasks.scan_url, "delay", queued.append)

    none = await client.post("/api/v1/scans", headers=auth_headers, json={"url": "https://shop.example.com"})
    assert none.status_code == 422 and "project" in none.json()["detail"]
    other = await client.post("/api/v1/scans", headers=auth_headers, json={"url": "https://shop.example.com", "project_id": "not-mine"})
    assert other.status_code == 422

    project = (await client.post("/api/v1/projects", headers=auth_headers, json={"name": "Shop", "base_url": "https://shop.example.com"})).json()
    bad = await client.post("/api/v1/scans", headers=auth_headers, json={"url": "shop.example.com", "project_id": project["id"]})
    assert bad.status_code == 422
    ok = await client.post("/api/v1/scans", headers=auth_headers, json={"url": "https://shop.example.com", "project_id": project["id"], "profile": "pci_dss"})
    assert ok.status_code in (200, 201), ok.text
    scan = ok.json()
    assert scan["project_id"] == project["id"] and scan["scan_profile"] == "pci_dss" and queued == [scan["id"]]

    summary = (await client.get(f"/api/v1/scans/{scan['id']}", headers=auth_headers)).json()
    assert summary["vulnerability_count"] == 0 and summary["gap_count"] == 0
    assert queued == [scan["id"]]
