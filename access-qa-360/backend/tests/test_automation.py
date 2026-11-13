"""Comparing scans, the OWASP view, schedules, chat alerts, trackers and pull-request scans."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.secrets import decrypt
from app.models.audit_job import AuditJob, AuditStatus
from app.models.automation import ScanSchedule
from app.models.integration import Integration
from app.models.organization import Organization
from app.services import compliance, findings as F, notify, scan_control, schedules
from tests.conftest import TestSessionLocal

API = "/api/v1"
SLACK = "https://hooks.slack.com/services/T000/B000/XXXX"


def finding(title, severity="high", url="https://shop.example.com/api/users", **more):
    return {"title": title, "severity": severity, "affected_url": url, "check": more.pop("check", "headers"), **more}


async def org_id(client, headers) -> str:
    return (await client.get(f"{API}/auth/me", headers=headers)).json()["organization_id"]


async def add_scan(org, user, findings, days_ago=0, **more) -> str:
    async with TestSessionLocal() as db:
        now = datetime.now(timezone.utc) - timedelta(days=days_ago)
        job = AuditJob(created_by=user.id, organization_id=org, source_type=more.pop("source_type", "web"),
                       target_url=more.pop("target_url", "https://shop.example.com"), status=AuditStatus.completed,
                       tier3_result={"findings": findings}, risk_score=more.pop("risk_score", 40), created_at=now, started_at=now, **more)
        db.add(job)
        await db.commit()
        return job.id


@pytest.fixture
def launched(monkeypatch):
    started: list[str] = []
    monkeypatch.setattr(scan_control, "launch", started.append)
    return started


@pytest.fixture
def test_db(monkeypatch):
    for module in (notify, schedules):
        monkeypatch.setattr(module, "AsyncSessionLocal", TestSessionLocal)


# ---- findings, changes, standards --------------------------------------------

def test_fingerprints_ignore_line_numbers_and_case():
    job = lambda f: type("J", (), {"tier1_result": None, "tier2_result": None, "tier3_result": {"findings": f}, "source_filename": None})()
    a = F.all_findings(job([finding("Hardcoded secret", url="app/settings.py:14")]))
    b = F.all_findings(job([finding("hardcoded  SECRET", url="app/settings.py:92"), finding("Open redirect", "low")]))
    diff = F.compare(a, b)
    assert [f["title"] for f in diff["new"]] == ["Open redirect"] and diff["fixed"] == [] and diff["unchanged"] == 1


def test_findings_are_sorted_into_the_owasp_top_ten():
    cat = lambda **f: compliance.category({"source": "security", **f})
    assert cat(title="SQL injection in search") == "A03"
    assert cat(title="Package lodash is vulnerable", check="dependency") == "A06"
    assert cat(title="Missing Content-Security-Policy header") == "A05"
    assert cat(title="JWT accepts alg none") == "A07"
    assert cat(title="Anything", owasp_category="A01:2021 Broken Access Control") == "A01"
    assert cat(title="Site is slow") is None
    assert compliance.category({"source": "accessibility", "title": "Images need alt text"}) is None


async def test_changes_compare_with_the_scan_before(client: AsyncClient, test_user, auth_headers):
    org = await org_id(client, auth_headers)
    old = await add_scan(org, test_user, [finding("Missing HSTS header"), finding("SQL injection", "critical")], days_ago=7, risk_score=60)
    new = await add_scan(org, test_user, [finding("Missing HSTS header"), finding("Open CORS policy", "medium")], risk_score=30)
    other = await add_scan(org, test_user, [], target_url="https://other.example.com")

    r = (await client.get(f"{API}/audits/{new}/changes", headers=auth_headers)).json()
    assert r["baseline"]["id"] == old and r["unchanged"] == 1
    assert [f["title"] for f in r["new"]] == ["Open CORS policy"] and [f["title"] for f in r["fixed"]] == ["SQL injection"]
    assert [h["risk_score"] for h in r["history"]] == [60, 30]

    first = (await client.get(f"{API}/audits/{old}/changes", headers=auth_headers)).json()
    assert first["baseline"] is None and first["new"] == []
    assert (await client.get(f"{API}/audits/{new}/changes", params={"against": other}, headers=auth_headers)).status_code == 422

    s = (await client.get(f"{API}/audits/{old}/standards", headers=auth_headers)).json()
    by_code = {c["code"]: c for c in s["categories"]}
    assert by_code["A03"]["count"] == 1 and by_code["A03"]["worst"] == "critical" and s["covered"] == 2
    csv_text = (await client.get(f"{API}/audits/{old}/standards.csv", headers=auth_headers)).text
    assert "A03,Injection,critical,SQL injection" in csv_text


async def test_another_organisations_scan_cannot_be_read(client: AsyncClient, test_user, auth_headers):
    async with TestSessionLocal() as db:
        other = Organization(name="Other")
        db.add(other)
        await db.commit()
    theirs = await add_scan(other.id, test_user, [finding("x")])
    for path in ("changes", "standards", "standards.csv"):
        assert (await client.get(f"{API}/audits/{theirs}/{path}", headers=auth_headers)).status_code == 404


# ---- schedules ---------------------------------------------------------------

def test_schedule_dates():
    at = datetime(2026, 1, 31, 9, 0, tzinfo=timezone.utc)
    assert schedules.advance(at, "daily").day == 1 and schedules.advance(at, "weekly").day == 7
    assert schedules.advance(at, "monthly") == datetime(2026, 2, 28, 9, 0, tzinfo=timezone.utc)
    # A server that was off for ten days runs the schedule once and lands on the next free slot.
    assert schedules.next_after(at, "daily", at + timedelta(days=10, hours=1)) == at + timedelta(days=11)


async def test_schedule_rules(client: AsyncClient, test_user, auth_headers):
    body = {"source_type": "web", "target": "https://shop.example.com", "frequency": "weekly", "ownership_confirmed": True}
    assert (await client.post(f"{API}/schedules", headers=auth_headers, json={**body, "ownership_confirmed": False})).status_code == 400
    assert (await client.post(f"{API}/schedules", headers=auth_headers, json={**body, "target": "shop.example.com"})).status_code == 422
    assert (await client.post(f"{API}/schedules", headers=auth_headers, json={**body, "source_type": "repo", "target": "https://evil.example.com/a/b"})).status_code == 422
    assert (await client.post(f"{API}/schedules", headers=auth_headers, json={**body, "outputs": ["appium"]})).status_code == 422
    made = await client.post(f"{API}/schedules", headers=auth_headers, json=body)
    assert made.status_code == 201 and made.json()["outputs"] == ["security"]
    assert (await client.post(f"{API}/schedules", headers=auth_headers, json=body)).status_code == 409
    sid = made.json()["id"]
    assert (await client.patch(f"{API}/schedules/{sid}", headers=auth_headers, json={"active": False})).json()["active"] is False
    assert len((await client.get(f"{API}/schedules", headers=auth_headers)).json()) == 1
    assert (await client.delete(f"{API}/schedules/{sid}", headers=auth_headers)).status_code == 204
    assert (await client.get(f"{API}/schedules", headers=auth_headers)).json() == []


async def test_due_schedules_start_a_scan_once(client: AsyncClient, test_user, auth_headers, launched, test_db):
    made = (await client.post(f"{API}/schedules", headers=auth_headers, json={
        "source_type": "repo", "target": "https://github.com/acme/shop", "frequency": "daily", "ownership_confirmed": True})).json()
    assert await schedules.run_due() == []                                   # not due yet
    later = datetime.now(timezone.utc) + timedelta(days=1, minutes=5)
    started = await schedules.run_due(later)
    assert len(started) == 1 and launched == started
    assert await schedules.run_due(later) == []                              # already claimed for this slot
    async with TestSessionLocal() as db:
        job = await db.get(AuditJob, started[0])
        assert job.trigger == {"kind": "schedule", "schedule_id": made["id"]} and job.repo_url == "https://github.com/acme/shop.git"
        assert job.outputs == ["security"] and job.started_at and job.ownership_confirmed_at
        assert (await db.get(ScanSchedule, made["id"])).last_audit_id == job.id


async def test_a_schedule_is_skipped_when_the_scan_allowance_is_used(client: AsyncClient, test_user, auth_headers, launched, test_db):
    org = await org_id(client, auth_headers)
    made = (await client.post(f"{API}/schedules", headers=auth_headers, json={
        "source_type": "web", "target": "https://shop.example.com", "frequency": "daily", "ownership_confirmed": True})).json()
    async with TestSessionLocal() as db:
        (await db.get(Organization, org)).scan_limit = 1
        await db.commit()
    await add_scan(org, test_user, [])
    assert await schedules.run_due(datetime.now(timezone.utc) + timedelta(days=2)) == [] and launched == []
    listed = (await client.get(f"{API}/schedules", headers=auth_headers)).json()[0]
    assert listed["last_note"] == "Skipped: All 1 scans for this month are used"
    assert (await client.post(f"{API}/schedules/{made['id']}/run", headers=auth_headers)).status_code == 403


# ---- chat alerts -------------------------------------------------------------

def test_only_real_chat_webhook_addresses_are_accepted():
    assert notify.chat_url_ok("slack", SLACK)
    assert notify.chat_url_ok("teams", "https://acme.webhook.office.com/webhookb2/abc")
    for bad in ("http://hooks.slack.com/services/x", "https://hooks.slack.com.evil.io/x", "https://169.254.169.254/latest", "https://evilhooks.slack.com/x"):
        assert not notify.chat_url_ok("slack", bad)
    assert not notify.chat_url_ok("teams", "https://webhook.office.com.evil.io/x")


async def test_slack_gets_scheduled_scan_results_with_what_changed(client: AsyncClient, test_user, auth_headers, httpx_mock, test_db):
    httpx_mock.add_response(url=SLACK, method="POST", text="ok")
    assert (await client.put(f"{API}/org/connections/slack", headers=auth_headers, json={"webhook_url": "https://example.com/hook"})).status_code == 400
    saved = await client.put(f"{API}/org/connections/slack", headers=auth_headers, json={"webhook_url": SLACK})
    assert saved.status_code == 200 and saved.json() == {"connected": True, "events": "automatic"}
    org = await org_id(client, auth_headers)
    async with TestSessionLocal() as db:
        row = (await db.execute(select(Integration).where(Integration.kind == "slack"))).scalar_one()
        assert SLACK not in row.secret_encrypted and decrypt(row.secret_encrypted) == SLACK

    await add_scan(org, test_user, [finding("Missing HSTS header")], days_ago=7)
    by_hand = await add_scan(org, test_user, [finding("Missing HSTS header")], days_ago=1)
    await notify.scan_finished(by_hand)
    assert len(httpx_mock.get_requests()) == 1                              # only the test message: scans run by hand stay quiet

    httpx_mock.add_response(url=SLACK, method="POST", text="ok")
    scheduled = await add_scan(org, test_user, [finding("Missing HSTS header"), finding("SQL injection", "critical")], trigger={"kind": "schedule", "schedule_id": "s"})
    await notify.scan_finished(scheduled)
    text = json.loads(httpx_mock.get_requests()[-1].content)["text"]
    assert "2 findings: 1 critical, 1 high" in text and "1 new, 0 fixed" in text and "[critical] SQL injection" in text
    assert f"/audits/{scheduled}" in text

    assert (await client.delete(f"{API}/org/connections/slack", headers=auth_headers)).status_code == 204
    assert (await client.get(f"{API}/org/connections", headers=auth_headers)).json()["slack"] == {"connected": False}


# ---- GitHub: issues and pull requests ----------------------------------------

def github_ok(httpx_mock, repo="acme/shop"):
    httpx_mock.add_response(url="https://api.github.com/user", json={"login": "octo"})
    httpx_mock.add_response(url=f"https://api.github.com/repos/{repo}", json={"full_name": repo})


async def connect_github(client, headers, httpx_mock, **more) -> dict:
    github_ok(httpx_mock)
    r = await client.put(f"{API}/org/github", headers=headers, json={"token": "ghp_exampletoken123", "repo": "acme/shop", **more})
    assert r.status_code == 200
    return r.json()


async def test_a_finding_becomes_a_github_issue(client: AsyncClient, test_user, auth_headers, httpx_mock):
    httpx_mock.add_response(url="https://api.github.com/user", status_code=401, json={})
    assert (await client.put(f"{API}/org/github", headers=auth_headers, json={"token": "bad-token-000", "repo": "acme/shop"})).status_code == 400
    assert (await client.put(f"{API}/org/github", headers=auth_headers, json={"token": "ghp_exampletoken123", "repo": "not a repo"})).status_code == 422
    await connect_github(client, auth_headers, httpx_mock)
    scan = await add_scan(await org_id(client, auth_headers), test_user, [finding("SQL injection", "critical", remediation="Use parameters")])
    httpx_mock.add_response(url="https://api.github.com/repos/acme/shop/issues", method="POST", json={"number": 12, "html_url": "https://github.com/acme/shop/issues/12"})
    r = await client.post(f"{API}/audits/{scan}/issues", headers=auth_headers, json={"source": "security", "index": 0})
    assert r.status_code == 201 and r.json()["issue_key"] == "#12"
    sent = json.loads(httpx_mock.get_requests()[-1].content)
    assert sent["title"] == "[Critical] SQL injection" and "Use parameters" in sent["body"]
    again = await client.post(f"{API}/audits/{scan}/issues", headers=auth_headers, json={"source": "security", "index": 0})
    assert again.json()["issue_key"] == "#12" and len(httpx_mock.get_requests()) == 4      # no second issue


def signed(secret: str, event: dict) -> tuple[bytes, dict]:
    payload = json.dumps(event).encode()
    return payload, {"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()}


def pr_event(action="opened", head="acme/shop", private=False):
    return {"action": action, "pull_request": {"number": 7, "head": {"sha": "abc123", "ref": "feature/login", "repo": {"full_name": head}},
                                               "base": {"repo": {"full_name": "acme/shop", "private": private}}}}


async def test_a_pull_request_starts_a_scan_of_its_branch(client: AsyncClient, test_user, auth_headers, httpx_mock, launched):
    conn = await connect_github(client, auth_headers, httpx_mock)
    org = await org_id(client, auth_headers)
    hook = f"{API}/integrations/github/webhook/{org}"
    assert conn["webhook_url"].endswith(hook) and len(conn["webhook_secret"]) == 48

    payload, headers = signed("wrong-secret", pr_event())
    assert (await client.post(hook, content=payload, headers=headers)).status_code == 401
    payload, headers = signed(conn["webhook_secret"], pr_event("closed"))
    assert (await client.post(hook, content=payload, headers=headers)).json()["scan"] is None

    httpx_mock.add_response(url="https://api.github.com/repos/acme/shop/statuses/abc123", method="POST", json={})
    payload, headers = signed(conn["webhook_secret"], pr_event(private=True))
    scan = (await client.post(hook, content=payload, headers=headers)).json()["scan"]
    assert launched == [scan]
    assert json.loads(httpx_mock.get_requests()[-1].content)["state"] == "pending"
    async with TestSessionLocal() as db:
        job = await db.get(AuditJob, scan)
        assert job.repo_url == "https://github.com/acme/shop.git" and job.repo_ref == "feature/login" and job.created_by == test_user.id
        assert job.trigger == {"kind": "pull_request", "repo": "acme/shop", "number": 7, "sha": "abc123", "branch": "feature/login", "private": True}

    # A fork's branch is fetched without the organisation's token.
    httpx_mock.add_response(url="https://api.github.com/repos/acme/shop/statuses/abc123", method="POST", json={})
    payload, headers = signed(conn["webhook_secret"], pr_event(head="stranger/shop", private=True))
    fork = (await client.post(hook, content=payload, headers=headers)).json()["scan"]
    async with TestSessionLocal() as db:
        job = await db.get(AuditJob, fork)
        assert job.repo_url == "https://github.com/stranger/shop.git" and job.trigger["private"] is False


async def test_the_result_is_posted_on_the_pull_request(client: AsyncClient, test_user, auth_headers, httpx_mock, test_db):
    await connect_github(client, auth_headers, httpx_mock)
    org = await org_id(client, auth_headers)
    repo = {"source_type": "repo", "target_url": None, "repo_url": "https://github.com/acme/shop.git"}
    await add_scan(org, test_user, [finding("Old issue", "high", "app/a.py:3")], days_ago=3, **repo)
    pr = await add_scan(org, test_user, [finding("Old issue", "high", "app/a.py:9"), finding("Hardcoded secret", "critical", "app/b.py:1")],
                        repo_ref="feature/login", trigger={"kind": "pull_request", "repo": "acme/shop", "number": 7, "sha": "abc123", "branch": "feature/login"}, **repo)
    httpx_mock.add_response(url="https://api.github.com/repos/acme/shop/issues/7/comments", method="POST", json={})
    httpx_mock.add_response(url="https://api.github.com/repos/acme/shop/statuses/abc123", method="POST", json={})
    await notify.scan_finished(pr)
    comment, status = [json.loads(r.content) for r in httpx_mock.get_requests()[-2:]]
    assert "**1 new**, 0 fixed" in comment["body"] and "| Critical | Hardcoded secret | app/b.py:1 |" in comment["body"] and "Old issue" not in comment["body"]
    assert status["state"] == "failure" and status["description"] == "1 new finding at high severity or above" and status["context"] == "Wiseflow"


def test_pull_request_status_rules():
    job = type("J", (), {"status": AuditStatus.completed})()
    high = [{"severity": "high"}]
    assert notify.pr_state(job, high, {"new": [], "fixed": []}, "high")[0] == "success"      # nothing new: older findings do not block
    assert notify.pr_state(job, high, None, "high")[0] == "failure"                           # nothing to compare with: all count
    assert notify.pr_state(job, high, None, "critical")[0] == "success"
    assert notify.pr_state(job, high, None, "never")[0] == "success"
    job.status = AuditStatus.failed
    assert notify.pr_state(job, [], None, "high")[0] == "error"


# ---- Linear, members, audit log ----------------------------------------------

async def test_linear_team_is_checked_and_used(client: AsyncClient, test_user, auth_headers, httpx_mock):
    httpx_mock.add_response(url="https://api.linear.app/graphql", method="POST", json={"data": {"teams": {"nodes": []}}})
    assert (await client.put(f"{API}/org/linear", headers=auth_headers, json={"api_key": "lin_api_example", "team_key": "eng"})).status_code == 400
    httpx_mock.add_response(url="https://api.linear.app/graphql", method="POST", json={"data": {"teams": {"nodes": [{"id": "team-1", "name": "Engineering"}]}}})
    saved = await client.put(f"{API}/org/linear", headers=auth_headers, json={"api_key": "lin_api_example", "team_key": "eng"})
    assert saved.json() == {"connected": True, "team_key": "ENG", "team_name": "Engineering"}
    scan = await add_scan(await org_id(client, auth_headers), test_user, [finding("Open CORS policy", "medium")])
    httpx_mock.add_response(url="https://api.linear.app/graphql", method="POST",
                            json={"data": {"issueCreate": {"success": True, "issue": {"identifier": "ENG-4", "url": "https://linear.app/acme/issue/ENG-4"}}}})
    r = await client.post(f"{API}/audits/{scan}/issues", headers=auth_headers, json={"source": "security", "index": 0, "tracker": "linear"})
    assert r.status_code == 201 and r.json()["issue_key"] == "ENG-4"
    assert json.loads(httpx_mock.get_requests()[-1].content)["variables"]["i"]["teamId"] == "team-1"


async def test_only_owners_and_admins_change_connections(client: AsyncClient, test_user, auth_headers):
    async with TestSessionLocal() as db:
        from app.models.user import User

        await client.get(f"{API}/auth/me", headers=auth_headers)
        (await db.get(User, test_user.id)).org_role = "member"
        await db.commit()
    assert (await client.put(f"{API}/org/connections/slack", headers=auth_headers, json={"webhook_url": SLACK})).status_code == 403
    assert (await client.put(f"{API}/org/github", headers=auth_headers, json={"token": "ghp_exampletoken123"})).status_code == 403
    assert (await client.delete(f"{API}/org/connections/github", headers=auth_headers)).status_code == 403
    assert (await client.get(f"{API}/org/connections", headers=auth_headers)).status_code == 200
