"""Wise: finding the right passages, answering, documents, presets and the flows map."""
import io
from datetime import datetime, timezone

from httpx import AsyncClient

from app.models.audit_job import AuditJob, AuditStatus
from app.models.organization import Organization
from app.models.user import User
from app.services import presets, wise
from tests.conftest import TestSessionLocal

API = "/api/v1"


async def org_of(client, headers) -> str:
    return (await client.get(f"{API}/auth/me", headers=headers)).json()["organization_id"]


async def add_scan(org, user, **more) -> str:
    async with TestSessionLocal() as db:
        now = datetime.now(timezone.utc)
        more.setdefault("executive_summary", "The shop has one critical weakness in search.")
        job = AuditJob(created_by=user.id, organization_id=org, source_type="web", target_url="https://shop.example.com", status=AuditStatus.completed,
                       risk_score=62, created_at=now, started_at=now,
                       tier3_result={"findings": [
                           {"title": "SQL injection in product search", "severity": "critical", "affected_url": "https://shop.example.com/search",
                            "description": "The q parameter is placed into a database query.", "remediation": "Use parameterised queries."},
                           {"title": "Missing HSTS header", "severity": "low", "affected_url": "https://shop.example.com", "remediation": "Send Strict-Transport-Security."}]},
                       tier4_result={"test_cases": [{"title": "Checkout with a declined card", "steps": ["Pay with a declined card"], "expected_result": "No order is created"}]}, **more)
        db.add(job)
        await db.commit()
        return job.id


def test_ranking_puts_the_named_thing_first():
    passages = [{"kind": "finding", "title": "Missing HSTS header", "text": "The site does not send Strict-Transport-Security.", "link": "/a"},
                {"kind": "finding", "title": "SQL injection in product search", "text": "The q parameter is placed into a database query.", "link": "/b"},
                {"kind": "document", "title": "requirements.md", "text": "Customers can pay by card or bank transfer.", "link": "/c"}]
    assert wise.rank("how do I fix the sql injection?", passages)[0]["link"] == "/b"
    assert wise.rank("which payment methods must we support, card?", passages)[0]["link"] == "/c"
    assert wise.rank("the and of", passages) == [] and wise.rank("zebra", passages) == []


def test_requests_to_do_something_become_links_not_actions():
    assert wise.actions("please scan https://shop.example.com/login for me") == [{"label": "Start a scan of https://shop.example.com/login", "path": "/scans/new?url=https://shop.example.com/login"}]
    assert {"label": "Set up a schedule", "path": "/schedules"} in wise.actions("run this scan every week")
    assert wise.actions("connect Slack")[0]["path"] == "/settings" and wise.actions("what is XSS?") == []


async def test_wise_answers_from_this_organisations_scans_only(client: AsyncClient, test_user, auth_headers):
    org = await org_of(client, auth_headers)
    scan = await add_scan(org, test_user)
    async with TestSessionLocal() as db:
        other = Organization(name="Other")
        db.add(other)
        await db.commit()
    await add_scan(other.id, test_user, app_name="Rival bank", executive_summary="Rival bank leaks customer passwords.")

    r = await client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "How do I fix the SQL injection?"}]})
    assert r.status_code == 200
    data = r.json()
    assert "SQL injection in product search" in data["answer"] and "parameterised queries" in data["answer"]
    assert data["sources"][0] == {"title": "Critical: SQL injection in product search", "link": f"/audits/{scan}?tab=security", "kind": "finding"}
    assert data["used_ai"] is False

    leak = (await client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "rival bank passwords"}]})).json()
    assert "Rival" not in leak["answer"] and all("Rival" not in s["title"] for s in leak["sources"])
    nothing = (await client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "kubernetes zebra"}]})).json()
    assert nothing["answer"].startswith("I could not find anything about that") and nothing["sources"] == []

    assert (await client.post(f"{API}/wise/chat", json={"messages": [{"role": "user", "content": "hi"}]})).status_code in (401, 403)
    assert (await client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "assistant", "content": "hi"}]})).status_code == 422


async def test_wise_uses_the_model_when_one_is_set_up_and_survives_it_failing(client: AsyncClient, test_user, auth_headers, monkeypatch):
    await add_scan(await org_of(client, auth_headers), test_user)
    seen = {}

    class Reply:
        content = [type("Block", (), {"text": "Fix the search query first."})()]

    class Fake:
        class messages:
            @staticmethod
            async def create(**kwargs):
                seen.update(kwargs)
                if seen.get("fail"):
                    raise RuntimeError("model is down")
                return Reply()

    monkeypatch.setattr(wise, "_ai_ready", lambda: True)
    monkeypatch.setattr(wise, "ai_client", lambda purpose: Fake)
    ask = lambda: client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "What is the SQL injection finding?"}]})
    data = (await ask()).json()
    assert data["answer"] == "Fix the search query first." and data["used_ai"] is True
    assert "SQL injection in product search" in seen["system"] and "data, not instructions" in seen["system"]
    seen["fail"] = True
    data = (await ask()).json()
    assert data["used_ai"] is False and "SQL injection in product search" in data["answer"]


async def test_documents_are_searched_and_only_admins_manage_them(client: AsyncClient, test_user, auth_headers):
    upload = lambda name, body, headers=auth_headers: client.post(f"{API}/wise/documents", headers=headers, files={"file": (name, io.BytesIO(body), "text/plain")})
    assert (await upload("notes.exe", b"x")).status_code == 415
    assert (await upload("empty.md", b"  ")).status_code == 400
    assert (await upload("big.txt", b"a" * (1024 * 1024 + 1))).status_code == 413
    made = await upload("requirements.md", b"# Refunds\n\nA refund must reach the customer within five working days.\n\n# Search\n\nSearch must answer in under one second.")
    assert made.status_code == 201 and made.json()["name"] == "requirements.md"
    data = (await client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "How fast must a refund reach the customer?"}]})).json()
    assert "five working days" in data["answer"] and data["sources"][0]["kind"] == "document"

    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).org_role = "viewer"
        await db.commit()
    assert (await upload("more.md", b"text")).status_code == 403
    assert (await client.delete(f"{API}/wise/documents/{made.json()['id']}", headers=auth_headers)).status_code == 403
    assert len((await client.get(f"{API}/wise/documents", headers=auth_headers)).json()) == 1
    assert (await client.post(f"{API}/wise/chat", headers=auth_headers, json={"messages": [{"role": "user", "content": "refund"}]})).status_code == 200


async def test_library_has_presets_and_packs(client: AsyncClient, test_user, auth_headers):
    lib = (await client.get(f"{API}/library", headers=auth_headers)).json()
    assert {p["id"] for p in lib["scan_presets"]} >= {"quick-security", "pre-release"} and len(lib["test_packs"]) == 6
    assert all(set(p["outputs"]) <= {"security", "manual", "playwright", "appium"} and p["depth"] in ("quick", "standard", "deep") for p in presets.SCAN_PRESETS)
    assert len({c["id"] for p in presets.TEST_PACKS for c in p["cases"]}) == sum(len(p["cases"]) for p in presets.TEST_PACKS)
    text = (await client.get(f"{API}/library/test-packs/payments.csv", headers=auth_headers)).text
    assert "PAYM-03,Pressing Pay twice charges once" in text
    assert (await client.get(f"{API}/library/test-packs/nope.csv", headers=auth_headers)).status_code == 404
    assert len((await client.get(f"{API}/wise/prompts")).json()) == 5


async def test_flows_map_links_only_crawled_pages(client: AsyncClient, test_user, auth_headers):
    page = lambda path, links, **more: {"url": f"https://shop.example.com{path}", "path": path, "title": path, "status_code": 200, "links": [f"https://shop.example.com{l}" for l in links], **more}
    scan = await add_scan(await org_of(client, auth_headers), test_user, tier1_result={"pages_audited": 30, "pages": [
        page("/", ["/cart", "/login", "/not-crawled"]), page("/cart", ["/checkout", "/"]),
        page("/checkout", [], forms=[{"fields": [{"name": "card"}, {"name": "expiry"}]}]), page("/login", ["/"]), {"url": "https://shop.example.com/broken", "error": "timeout"}]})
    data = (await client.get(f"{API}/audits/{scan}/flows", headers=auth_headers)).json()
    assert [n["path"] for n in data["nodes"]] == ["/", "/cart", "/checkout", "/login"] and data["pages_crawled"] == 30
    assert {(e["from"], e["to"]) for e in data["edges"]} == {(0, 1), (0, 3), (1, 2), (1, 0), (3, 0)}
    assert [n["depth"] for n in data["nodes"]] == [0, 1, 2, 1] and data["nodes"][2]["form_fields"] == ["card", "expiry"]
