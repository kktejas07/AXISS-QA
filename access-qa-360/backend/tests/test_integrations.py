"""API keys for pipelines and sending findings to Jira."""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.routes import audits as audits_routes
from app.models.audit_job import AuditJob, AuditStatus
from app.models.integration import ApiKey, Integration
from app.models.user import User
from tests.conftest import TestSessionLocal

KEYS = "/api/v1/org/api-keys"
JIRA = "/api/v1/org/integrations/jira"
SITE = "https://acme.atlassian.net"
GOOD = {"base_url": SITE + "/", "email": "qa@acme.io", "api_token": "jira-token-123", "project_key": "sec", "issue_type": "Bug"}


@pytest.fixture
def launched(monkeypatch):
    started: list[str] = []
    monkeypatch.setattr(audits_routes, "_launch", started.append)
    return started


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_api_key_runs_scans_but_cannot_manage_anything(client: AsyncClient, test_user, auth_headers, launched):
    created = await client.post(KEYS, headers=auth_headers, json={"name": "GitHub Actions"})
    assert created.status_code == 201, created.text
    token = created.json()["key"]
    assert token.startswith("wf_") and created.json()["prefix"] == token[:10]

    # Only a hash is stored, and the list never shows the key again.
    async with TestSessionLocal() as db:
        (row,) = (await db.execute(select(ApiKey))).scalars().all()
    assert token not in (row.key_hash, row.prefix) and len(row.key_hash) == 64
    listed = (await client.get(KEYS, headers=auth_headers)).json()
    assert [k["name"] for k in listed] == ["GitHub Actions"] and listed[0]["key"] is None and listed[0]["last_used_at"] is None

    # The key starts a scan and reads it back.
    scan = await client.post("/api/v1/audits", headers=bearer(token), json={"target_url": "https://shop.example.com"})
    assert scan.status_code == 201, scan.text
    assert launched == [scan.json()["id"]]
    assert (await client.get(f"/api/v1/audits/{scan.json()['id']}", headers=bearer(token))).status_code == 200
    assert (await client.get(KEYS, headers=auth_headers)).json()[0]["last_used_at"] is not None

    # It cannot manage keys, people, settings, Jira or a password.
    for method, path, body in (
        ("get", KEYS, None), ("post", KEYS, {"name": "x"}), ("patch", "/api/v1/org", {"name": "Taken over"}),
        ("post", "/api/v1/org/invites", {"email": "x@acme.io", "role": "admin"}), ("put", JIRA, GOOD),
        ("post", "/api/v1/auth/change-password", {"current_password": "testpass123", "new_password": "another-pass-1"}),
        ("get", "/api/v1/admin/users", None),
    ):
        r = await client.request(method, path, headers=bearer(token), json=body)
        assert r.status_code == 403, (path, r.status_code, r.text)

    # Revoked keys stop working at once; made-up keys never work.
    assert (await client.delete(f"{KEYS}/{created.json()['id']}", headers=auth_headers)).status_code == 204
    assert (await client.get("/api/v1/audits", headers=bearer(token))).status_code == 401
    assert (await client.get("/api/v1/audits", headers=bearer("wf_not-a-real-key"))).status_code == 401
    assert (await client.get(KEYS, headers=auth_headers)).json() == []


async def test_api_key_dies_when_its_owner_is_deactivated(client: AsyncClient, test_user, auth_headers):
    token = (await client.post(KEYS, headers=auth_headers, json={"name": "CI"})).json()["key"]
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).is_active = False
        await db.commit()
    assert (await client.get("/api/v1/audits", headers=bearer(token))).status_code == 401


def jira_ok(httpx_mock, types=("Bug", "Task")):
    httpx_mock.add_response(url=f"{SITE}/rest/api/3/myself", json={"accountId": "1"})
    httpx_mock.add_response(url=f"{SITE}/rest/api/3/project/SEC", json={"name": "Security", "issueTypes": [{"name": t} for t in types]})


async def test_jira_is_checked_before_it_is_saved_and_the_token_is_encrypted(client: AsyncClient, test_user, auth_headers, httpx_mock):
    assert (await client.get(JIRA, headers=auth_headers)).json()["connected"] is False

    for bad in ("http://acme.atlassian.net", "https://evil.example.com", "https://169.254.169.254", "https://acme.atlassian.net.evil.com", "https://user@acme.atlassian.net"):
        r = await client.put(JIRA, headers=auth_headers, json={**GOOD, "base_url": bad})
        assert r.status_code == 400 and "atlassian.net" in r.json()["detail"], bad

    httpx_mock.add_response(url=f"{SITE}/rest/api/3/myself", status_code=401)
    r = await client.put(JIRA, headers=auth_headers, json=GOOD)
    assert r.status_code == 400 and "API token" in r.json()["detail"]

    jira_ok(httpx_mock, types=("Task", "Story"))
    r = await client.put(JIRA, headers=auth_headers, json=GOOD)
    assert r.status_code == 400 and "Task, Story" in r.json()["detail"]

    jira_ok(httpx_mock)
    r = await client.put(JIRA, headers=auth_headers, json=GOOD)
    assert r.status_code == 200, r.text
    assert r.json() == {"connected": True, "base_url": SITE, "email": "qa@acme.io", "project_key": "SEC", "project_name": "Security", "issue_type": "Bug"}
    async with TestSessionLocal() as db:
        (row,) = (await db.execute(select(Integration))).scalars().all()
    assert "jira-token-123" not in row.secret_encrypted and "jira-token-123" not in str(row.config)
    assert "api_token" not in (await client.get(JIRA, headers=auth_headers)).json()

    assert (await client.delete(JIRA, headers=auth_headers)).status_code == 204
    assert (await client.get(JIRA, headers=auth_headers)).json()["connected"] is False


async def test_a_finding_becomes_one_jira_issue(client: AsyncClient, test_user, auth_headers, httpx_mock):
    async with TestSessionLocal() as db:
        me = await db.get(User, test_user.id)
        job = AuditJob(
            created_by=me.id, organization_id=me.organization_id, target_url="https://shop.example.com", status=AuditStatus.completed,
            started_at=datetime.now(timezone.utc),
            tier3_result={"findings": [
                {"severity": "critical", "title": "Token signature is not checked", "description": "Anyone can forge a session.", "affected_url": "https://shop.example.com/api/me", "method": "GET", "remediation": "Verify the signature.", "cwe_id": "CWE-347", "proof_request": "GET /api/me"},
            ]},
        )
        db.add(job)
        await db.commit()
        job_id = job.id
    url = f"/api/v1/audits/{job_id}/issues"

    not_connected = await client.post(url, headers=auth_headers, json={"source": "security", "index": 0})
    assert not_connected.status_code == 400 and "not connected" in not_connected.json()["detail"]

    jira_ok(httpx_mock)
    assert (await client.put(JIRA, headers=auth_headers, json=GOOD)).status_code == 200
    assert (await client.post(url, headers=auth_headers, json={"source": "security", "index": 5})).status_code == 404

    httpx_mock.add_response(url=f"{SITE}/rest/api/3/issue", method="POST", status_code=201, json={"id": "10001", "key": "SEC-42"})
    made = await client.post(url, headers=auth_headers, json={"source": "security", "index": 0})
    assert made.status_code == 201, made.text
    assert made.json() == {"finding_ref": "security:0", "issue_key": "SEC-42", "issue_url": f"{SITE}/browse/SEC-42"}

    sent = [r for r in httpx_mock.get_requests() if r.url.path == "/rest/api/3/issue"]
    import json
    fields = json.loads(sent[0].content)["fields"]
    assert fields["project"] == {"key": "SEC"} and fields["issuetype"] == {"name": "Bug"}
    assert fields["summary"] == "[Critical] Token signature is not checked" and "severity-critical" in fields["labels"]
    assert "Verify the signature." in json.dumps(fields["description"]) and f"/audits/{job_id}" in json.dumps(fields["description"])

    # Asking again returns the same issue instead of creating a duplicate.
    again = await client.post(url, headers=auth_headers, json={"source": "security", "index": 0})
    assert again.json()["issue_key"] == "SEC-42" and len([r for r in httpx_mock.get_requests() if r.url.path == "/rest/api/3/issue"]) == 1
    assert (await client.get(url, headers=auth_headers)).json() == [made.json()]
