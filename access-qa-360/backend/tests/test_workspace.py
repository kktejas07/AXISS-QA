"""The findings inbox, SBOM download, notifications and the getting-started checklist."""
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient

from app.models.audit_job import AuditJob, AuditStatus
from app.models.organization import Organization
from app.models.user import User
from tests.conftest import TestSessionLocal

API = "/api/v1"


async def org_of(client, headers) -> str:
    return (await client.get(f"{API}/auth/me", headers=headers)).json()["organization_id"]


async def scan(org, user, findings, days_ago=0, **more) -> str:
    async with TestSessionLocal() as db:
        at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        more.setdefault("target_url", "https://shop.example.com")
        job = AuditJob(created_by=user.id, organization_id=org, source_type=more.pop("source_type", "web"), status=more.pop("status", AuditStatus.completed),
                       created_at=at, started_at=at, completed_at=at, critical_count=sum(1 for f in findings if f["severity"] == "critical"),
                       tier3_result={"findings": findings}, **more)
        db.add(job)
        await db.commit()
        return job.id


def finding(title, severity="high", url="https://shop.example.com/api"):
    return {"title": title, "severity": severity, "affected_url": url}


async def test_a_decision_about_a_finding_follows_it_to_the_next_scan(client: AsyncClient, test_user, auth_headers):
    org = await org_of(client, auth_headers)
    old = await scan(org, test_user, [finding("SQL injection", "critical"), finding("Missing HSTS header", "low")], days_ago=7)
    inbox = (await client.get(f"{API}/findings", headers=auth_headers)).json()
    assert inbox["counts"] == {"open": 2, "fixed": 0, "accepted": 0, "false_positive": 0} and [i["title"] for i in inbox["items"]] == ["SQL injection", "Missing HSTS header"]

    put = lambda **body: client.put(f"{API}/findings/state", headers=auth_headers, json={"audit_id": old, "source": "security", **body})
    assert (await put(index=1, status="accepted")).status_code == 422                                   # must say why
    assert (await put(index=9, status="fixed")).status_code == 404
    assert (await put(index=1, status="open", assignee_id="someone-else")).status_code == 422
    done = await put(index=1, status="accepted", note="Behind a CDN that sets it.", assignee_id=test_user.id)
    assert done.status_code == 200 and done.json()["status"] == "accepted"

    # A newer scan of the same site: the same finding at a different position keeps its decision.
    new = await scan(org, test_user, [finding("Missing HSTS header", "low"), finding("Open CORS policy", "medium")])
    inbox = (await client.get(f"{API}/findings", headers=auth_headers)).json()
    assert inbox["total"] == 2 and all(i["audit_id"] == new for i in inbox["items"])                    # only the latest scan of each target
    hsts = next(i for i in inbox["items"] if i["title"] == "Missing HSTS header")
    assert (hsts["status"], hsts["note"], hsts["assignee"]) == ("accepted", "Behind a CDN that sets it.", "Test User")
    assert [i["title"] for i in (await client.get(f"{API}/findings", params={"status": "open"}, headers=auth_headers)).json()["items"]] == ["Open CORS policy"]
    assert len((await client.get(f"{API}/findings", params={"assignee": "me"}, headers=auth_headers)).json()["items"]) == 1
    assert len((await client.get(f"{API}/findings", params={"severity": "critical"}, headers=auth_headers)).json()["items"]) == 0


async def test_the_inbox_is_per_organisation_and_viewers_cannot_decide(client: AsyncClient, test_user, auth_headers):
    org = await org_of(client, auth_headers)
    mine = await scan(org, test_user, [finding("Mine")])
    async with TestSessionLocal() as db:
        other = Organization(name="Other")
        db.add(other)
        await db.commit()
    theirs = await scan(other.id, test_user, [finding("Theirs")], target_url="https://rival.example.com")
    assert [i["title"] for i in (await client.get(f"{API}/findings", headers=auth_headers)).json()["items"]] == ["Mine"]
    body = {"source": "security", "index": 0, "status": "fixed"}
    assert (await client.put(f"{API}/findings/state", headers=auth_headers, json={"audit_id": theirs, **body})).status_code == 404
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).org_role = "viewer"
        await db.commit()
    assert (await client.put(f"{API}/findings/state", headers=auth_headers, json={"audit_id": mine, **body})).status_code == 403
    assert (await client.get(f"{API}/findings", headers=auth_headers)).status_code == 200


async def test_sbom_lists_the_packages_a_code_scan_found(client: AsyncClient, test_user, auth_headers):
    org = await org_of(client, auth_headers)
    code = await scan(org, test_user, [], source_type="repo", target_url=None, repo_url="https://github.com/acme/shop.git",
                      tier1_result={"packages": [{"ecosystem": "PyPI", "name": "requests", "version": "2.31.0", "manifest": "requirements.txt"},
                                                 {"ecosystem": "npm", "name": "left-pad", "version": "1.3.0", "manifest": "package-lock.json"}]})
    r = await client.get(f"{API}/audits/{code}/sbom.json", headers=auth_headers)
    doc = r.json()
    assert r.status_code == 200 and (doc["bomFormat"], doc["specVersion"]) == ("CycloneDX", "1.5") and ".cdx.json" in r.headers["content-disposition"]
    assert [c["purl"] for c in doc["components"]] == ["pkg:pypi/requests@2.31.0", "pkg:npm/left-pad@1.3.0"] and doc["metadata"]["component"]["name"] == "acme/shop"
    web = await scan(org, test_user, [])
    assert (await client.get(f"{API}/audits/{web}/sbom.json", headers=auth_headers)).status_code == 404


async def test_notifications_and_first_steps(client: AsyncClient, test_user, auth_headers):
    org = await org_of(client, auth_headers)
    start = (await client.get(f"{API}/onboarding", headers=auth_headers)).json()
    assert (start["done"], start["total"]) == (0, 5) and start["steps"][0]["id"] == "scan"
    assert (await client.get(f"{API}/notifications", headers=auth_headers)).json() == []

    await scan(org, test_user, [finding("SQL injection", "critical")], days_ago=1, app_name="Shop")
    await scan(org, test_user, [], status=AuditStatus.failed, app_name="Blog", trigger={"kind": "schedule", "schedule_id": "s"})
    await scan(org, test_user, [], days_ago=30, app_name="Old")
    notes = (await client.get(f"{API}/notifications", headers=auth_headers)).json()
    assert [n["text"] for n in notes] == ["Scheduled scan of Blog could not be completed", "Scan of Shop finished: 1 critical, 0 high"]
    assert notes[0]["tone"] == "bad" and notes[1]["path"].startswith("/audits/")
    await client.post(f"{API}/schedules", headers=auth_headers, json={"source_type": "web", "target": "https://shop.example.com", "frequency": "weekly", "ownership_confirmed": True})
    now = (await client.get(f"{API}/onboarding", headers=auth_headers)).json()
    assert now["done"] == 2 and [s["id"] for s in now["steps"] if s["done"]] == ["scan", "schedule"]


def test_licences_are_sorted_by_what_they_ask_of_you():
    from app.services.licences import classify

    for licence, group in [("MIT", "permissive"), ("Apache-2.0", "permissive"), ("BSD-3-Clause", "permissive"), ("ISC", "permissive"),
                           ("GPL-3.0-or-later", "strong"), ("GNU General Public License v2 (GPLv2)", "strong"), ("AGPL-3.0", "strong"),
                           ("LGPL-2.1", "weak"), ("GNU Lesser General Public License v3", "weak"), ("MPL-2.0", "weak"),
                           ("MIT OR GPL-3.0", "permissive"),                 # you may pick the easier one
                           ("MIT AND GPL-3.0", "strong"),                    # both apply
                           ("(MIT OR Apache-2.0)", "permissive"), ("", "unknown"), (None, "unknown"), ("UNLICENSED", "unknown"), ("Custom EULA", "unknown")]:
        assert classify(licence) == group, licence


async def test_a_code_scan_lists_its_licences_once_and_keeps_them(client: AsyncClient, test_user, auth_headers, monkeypatch):
    import httpx

    from app.services import licences

    org = await org_of(client, auth_headers)
    packages = [{"ecosystem": "PyPI", "name": "requests", "version": "2.31.0", "manifest": "requirements.txt"},
                {"ecosystem": "PyPI", "name": "mystery", "version": "0.1.0", "manifest": "requirements.txt"},
                {"ecosystem": "npm", "name": "@scope/copyleft", "version": "1.0.0", "manifest": "package-lock.json"},
                {"ecosystem": "npm", "name": "left-pad", "version": "1.3.0", "manifest": "package-lock.json"},
                {"ecosystem": "Maven", "name": "org.example:lib", "version": "1.0", "manifest": "pom.xml"}]
    job = await scan(org, test_user, [], source_type="code", target_url=None, app_name="shop-api", tier1_result={"packages": packages})
    plain = await scan(org, test_user, [], target_url="https://blog.example.com")
    assert (await client.get(f"{API}/audits/{plain}/licences", headers=auth_headers)).status_code == 404

    asked = []
    answers = {"https://pypi.org/pypi/requests/2.31.0/json": {"info": {"classifiers": ["License :: OSI Approved :: Apache Software License"]}},
               "https://registry.npmjs.org/@scope%2Fcopyleft/1.0.0": {"license": "GPL-3.0"},
               "https://registry.npmjs.org/left-pad/1.3.0": {"license": {"type": "WTFPL"}}}

    class Registry:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            asked.append(url)
            return httpx.Response(200, json=answers[url]) if url in answers else httpx.Response(404)

    monkeypatch.setattr(licences.httpx, "AsyncClient", Registry)
    got = (await client.get(f"{API}/audits/{job}/licences", headers=auth_headers)).json()
    assert got["counts"] == {"strong": 1, "unknown": 1, "weak": 0, "permissive": 2} and got["checked"] == 4 and got["not_looked_up"] == 1
    assert [(p["name"], p["licence"], p["group"]) for p in got["packages"]] == [
        ("@scope/copyleft", "GPL-3.0", "strong"), ("mystery", "Not found", "unknown"), ("left-pad", "WTFPL", "permissive"), ("requests", "Apache Software License", "permissive")]
    assert len(asked) == 4
    again = (await client.get(f"{API}/audits/{job}/licences", headers=auth_headers)).json()
    assert again == got and len(asked) == 4                                   # kept with the scan, not looked up twice


async def test_you_can_change_your_own_name(client: AsyncClient, test_user, auth_headers):
    assert (await client.patch(f"{API}/auth/me", headers=auth_headers, json={"full_name": "   "})).status_code == 422
    assert (await client.patch(f"{API}/auth/me", headers=auth_headers, json={"full_name": "  Erin   Q. Tester "})).json() == {"full_name": "Erin Q. Tester"}
    assert (await client.get(f"{API}/auth/me", headers=auth_headers)).json()["full_name"] == "Erin Q. Tester"
    assert (await client.patch(f"{API}/auth/me", json={"full_name": "Nobody"})).status_code in (401, 403)
