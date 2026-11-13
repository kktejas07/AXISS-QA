"""Source code and repository scans: the reader, the checks, and the API around them."""
import io
from datetime import datetime, timezone
import os
import zipfile

import pytest
from httpx import AsyncClient

from app.api.routes import audits as audits_routes
from app.core.config import settings
from app.models.audit_job import AuditJob, AuditStatus
from app.services import audit_orchestrator, code_auditor
from app.services.code_auditor import Package, SourceError
from tests.conftest import TestSessionLocal

AWS_KEY = "AKIA" + "IOSFODNN7EXAMPL2"   # shaped like a real key; split so this file is not itself a finding

PROJECT = {
    "app/main.py": (
        "from fastapi import APIRouter\n"
        "router = APIRouter(prefix='/api')\n\n"
        "@router.get('/users/{user_id}')\n"
        "def get_user(user_id, db):\n"
        "    return db.execute(f\"SELECT * FROM users WHERE id = {user_id}\")\n\n"
        "@router.post('/orders')\n"
        "def create_order(body):\n"
        "    return eval(body)\n"
    ),
    "app/billing.py": "import hashlib\n\n\ndef sign(value):\n    # eval( in a comment is not a finding\n    return hashlib.md5(value).hexdigest()\n",
    "app/docs.py": (
        "def helper(db, name):\n"
        "    \"\"\"Example::\n\n"
        "        @app.get('/from-a-docstring')\n"
        "        def view(): return eval(request.args['x'])\n"
        "    \"\"\"\n"
        "    return db.execute(f\"\"\"SELECT * FROM users\n"
        "        WHERE name = '{name}'\"\"\")\n"
    ),
    "tests/fixtures/.env": "SECRET_KEY=9f8e7d6c5b4a39281706\n",
    "app/settings.py": f"AWS_KEY = '{AWS_KEY}'\nDB_PASSWORD = 'changeme'\nAPI_KEY = 'k8Jq2mZx91LpQw7Rt5Vb'\nNAME = 'demo'\nPORT = 8000\n",
    "tests/test_main.py": "def test_get_user(client):\n    assert client.get('/api/users/1').status_code == 200\n\n\ndef test_main_loads():\n    import app.main\n",
    "web/src/Profile.tsx": "export function Profile({ bio }) {\n  const x = 1;\n  const y = 2;\n  const z = 3;\n  return <div dangerouslySetInnerHTML={{ __html: bio }} />;\n}\n",
    "requirements.txt": "requests==2.19.0\nflask>=2.0\n",
    "web/package-lock.json": '{"packages": {"": {}, "node_modules/lodash": {"version": "4.17.11"}}}',
    ".env": "SECRET_KEY=9f8e7d6c5b4a39281706\n",
    "Dockerfile": "FROM python:3.12\nCMD [\"python\", \"-m\", \"app\"]\n",
    "node_modules/evil/index.js": "eval(x)\n",
    "logo.png": "not really an image",
}


def make_zip(files: dict[str, str], wrap: str | None = "project-main") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(f"{wrap}/{name}" if wrap else name, text)
    return buf.getvalue()


@pytest.fixture
def tree(tmp_path):
    archive = tmp_path / "src.zip"
    archive.write_bytes(make_zip(PROJECT))
    dest = tmp_path / "src"
    dest.mkdir()
    code_auditor.extract_zip(str(archive), str(dest))
    return str(dest)


# ---- reading the source -----------------------------------------------------

def test_extract_keeps_code_and_drops_the_rest(tree):
    assert os.path.exists(os.path.join(tree, "app/main.py"))          # wrapper folder removed
    assert not os.path.exists(os.path.join(tree, "node_modules"))
    assert not os.path.exists(os.path.join(tree, "logo.png"))


def test_extract_ignores_paths_that_leave_the_folder(tmp_path):
    archive = tmp_path / "bad.zip"
    archive.write_bytes(make_zip({"../../escape.py": "x = 1\n", "ok.py": "y = 2\n"}, wrap=None))
    dest = tmp_path / "out"
    dest.mkdir()
    assert code_auditor.extract_zip(str(archive), str(dest)) == 1
    assert not (tmp_path / "escape.py").exists() and not (tmp_path.parent / "escape.py").exists()


def test_extract_refuses_non_archives_and_empty_ones(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"this is not a zip")
    with pytest.raises(SourceError):
        code_auditor.extract_zip(str(bad), str(tmp_path))
    empty = tmp_path / "empty.zip"
    empty.write_bytes(make_zip({"photo.png": "x"}))
    with pytest.raises(SourceError):
        code_auditor.extract_zip(str(empty), str(tmp_path))


@pytest.mark.parametrize("url,name", [
    ("https://github.com/acme/shop", "acme/shop"),
    ("https://github.com/acme/shop.git", "acme/shop"),
    ("https://github.com/acme/shop/tree/main/src", "acme/shop"),
    ("https://gitlab.com/group/sub/shop", "group/sub/shop"),
])
def test_repo_links_accepted(url, name):
    clone, short = code_auditor.parse_repo_url(url)
    assert short == name and clone.endswith(f"{name}.git") and clone.startswith("https://")


@pytest.mark.parametrize("url", [
    "", "github.com/acme/shop", "http://github.com/acme/shop", "git@github.com:acme/shop.git",
    "https://evil.example.com/acme/shop", "https://token@github.com/acme/shop", "https://github.com/acme",
    "https://github.com/acme/shop;rm -rf", "file:///etc/passwd", "https://169.254.169.254/latest/meta-data",
])
def test_repo_links_refused(url):
    with pytest.raises(SourceError):
        code_auditor.parse_repo_url(url)


# ---- the checks -------------------------------------------------------------

def test_scan_finds_secrets_risky_code_routes_and_gaps(tree):
    scan = code_auditor.scan_tree(tree, "standard")
    titles = {(f["title"], f["affected_url"]) for f in scan.findings}

    assert ("AWS access key in the code", "app/settings.py:1") in titles
    assert ("Hard-coded API key in the code", "app/settings.py:3") in titles
    assert not any("settings.py:2" in where for _, where in titles)     # 'changeme' is a placeholder
    assert ("SQL query built from strings", "app/main.py:6") in titles
    assert ("Text is run as code", "app/main.py:10") in titles
    assert ("Weak hash function", "app/billing.py:6") in titles
    assert not any(where.startswith("app/billing.py:5") for _, where in titles)   # commented line
    assert ("HTML is written without escaping", "web/src/Profile.tsx:5") in titles
    assert ("Environment file is part of the code", ".env") in titles
    assert ("Container runs as root", "Dockerfile") in titles
    # The secret itself is never stored in the finding.
    assert AWS_KEY not in str(scan.findings) and "9f8e7d6c5b4a39281706" not in str(scan.findings)
    # Worst first.
    assert scan.findings[0]["severity"] == "critical"

    # Examples in docstrings are not code, but a query that opens a triple-quoted string is.
    assert not any(where.startswith("app/docs.py:4") or where.startswith("app/docs.py:5") for _, where in titles)
    assert ("SQL query built from strings", "app/docs.py:7") in titles
    assert not any(where == "tests/fixtures/.env" for _, where in titles)

    routes = {(r["method"], r["path"]): r["tested"] for r in scan.routes}
    assert routes == {("GET", "/api/users/{user_id}"): True, ("POST", "/api/orders"): False}

    gaps = scan.qa_gaps
    assert gaps["test_files"] == 1 and gaps["untested_route_count"] == 1
    untested = {u["path"] for u in gaps["untested_files"]}
    assert "app/billing.py" in untested and "app/main.py" not in untested
    assert scan.languages == {"Python": 5, "TypeScript": 1}

    packages = {(p.ecosystem, p.name, p.version) for p in scan.packages}
    assert packages == {("PyPI", "requests", "2.19.0"), ("npm", "lodash", "4.17.11")}   # unpinned flask is left out


def test_scan_refuses_a_folder_with_no_code(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    with pytest.raises(SourceError):
        code_auditor.scan_tree(str(tmp_path))


async def test_dependencies_are_looked_up_and_grouped_per_package(httpx_mock):
    packages = [Package("PyPI", "requests", "2.19.0", "requirements.txt"), Package("npm", "left-pad", "1.3.0", "package-lock.json")]
    httpx_mock.add_response(url="https://api.osv.dev/v1/querybatch", json={"results": [
        {"vulns": [{"id": "GHSA-aaaa"}, {"id": "GHSA-bbbb"}]}, {},
    ]})
    httpx_mock.add_response(url="https://api.osv.dev/v1/vulns/GHSA-aaaa", json={
        "id": "GHSA-aaaa", "summary": "Credentials sent over plain HTTP on redirect",
        "database_specific": {"severity": "HIGH"},
        "affected": [{"package": {"name": "requests"}, "ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.20.0"}]}]}],
    })
    httpx_mock.add_response(url="https://api.osv.dev/v1/vulns/GHSA-bbbb", json={"id": "GHSA-bbbb", "summary": "Proxy header leak", "database_specific": {"severity": "MODERATE"}})

    findings, note = await code_auditor.check_dependencies(packages)
    assert note == {"packages_found": 2, "packages_checked": 2, "vulnerable": 1, "status": "checked"}
    (f,) = findings
    assert f["severity"] == "high" and f["title"] == "requests 2.19.0 has 2 known vulnerabilities"
    assert f["affected_url"] == "requirements.txt" and "2.20.0" in f["remediation"] and "GHSA-bbbb" in f["proof_request"]


async def test_dependency_check_says_so_when_the_database_is_unreachable(httpx_mock):
    httpx_mock.add_response(url="https://api.osv.dev/v1/querybatch", status_code=503)
    findings, note = await code_auditor.check_dependencies([Package("PyPI", "requests", "2.19.0", "requirements.txt")])
    assert findings == [] and note["status"] == "unavailable" and "not checked" in note["reason"] and "Error" not in note["reason"]


# ---- the API ----------------------------------------------------------------

@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "storage"))
    return tmp_path


@pytest.fixture
def launched(monkeypatch):
    started: list[str] = []
    monkeypatch.setattr(audits_routes, "_launch", started.append)
    return started


START = {"outputs": ["security", "manual"], "depth": "quick", "ownership_confirmed": True}


async def test_code_scan_needs_a_zip_before_it_starts(client: AsyncClient, auth_headers, launched):
    r = await client.post("/api/v1/audits", headers=auth_headers, json={"source_type": "code", "app_name": "Shop API"})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["started_at"] is None and job["allowed_outputs"] == ["security", "manual"] and launched == []
    base = f"/api/v1/audits/{job['id']}"

    assert (await client.post(f"{base}/start", headers=auth_headers, json=START)).status_code == 400
    r = await client.post(f"{base}/upload", headers=auth_headers, files={"file": ("shop.apk", b"x", "application/octet-stream")})
    assert r.status_code == 415
    r = await client.post(f"{base}/upload", headers=auth_headers, files={"file": ("shop.zip", make_zip(PROJECT), "application/zip")})
    assert r.status_code == 200 and r.json()["source_filename"] == "shop.zip"
    assert (await client.post(f"{base}/start", headers=auth_headers, json={**START, "outputs": ["playwright"]})).status_code == 422
    assert (await client.post(f"{base}/start", headers=auth_headers, json=START)).status_code == 200
    assert launched == [job["id"]]


async def test_repo_scan_checks_the_link(client: AsyncClient, auth_headers, launched):
    bad = await client.post("/api/v1/audits", headers=auth_headers, json={"source_type": "repo", "repo_url": "https://example.com/a/b"})
    assert bad.status_code == 422 and "GitHub" in bad.json()["detail"]
    r = await client.post("/api/v1/audits", headers=auth_headers, json={"source_type": "repo", "repo_url": "https://github.com/acme/shop/tree/main"})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["repo_url"] == "https://github.com/acme/shop.git" and job["label"] == "acme/shop" and job["target_url"] is None
    r = await client.post(f"/api/v1/audits/{job['id']}/upload", headers=auth_headers, files={"file": ("a.zip", b"x", "application/zip")})
    assert r.status_code == 415
    assert (await client.post(f"/api/v1/audits/{job['id']}/start", headers=auth_headers, json=START)).status_code == 200


async def test_code_scan_runs_end_to_end_and_deletes_the_upload(client: AsyncClient, test_user, auth_headers, storage, monkeypatch, httpx_mock):
    httpx_mock.add_response(url="https://api.osv.dev/v1/querybatch", json={"results": [{}, {}]})

    async def no_ai(job):
        raise RuntimeError("no key")

    monkeypatch.setattr(audit_orchestrator, "AsyncSessionLocal", TestSessionLocal)
    monkeypatch.setattr(audit_orchestrator, "_generate_unified_summary", no_ai)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")

    archive = storage / "upload.zip"
    archive.write_bytes(make_zip(PROJECT))
    async with TestSessionLocal() as db:
        job = AuditJob(created_by=test_user.id, organization_id=test_user.organization_id, source_type="code",
                       source_path=str(archive), source_filename="shop.zip", outputs=["security", "manual"], depth="quick",
                       started_at=datetime.now(timezone.utc))
        db.add(job)
        await db.commit()
        job_id = job.id

    await audit_orchestrator.run_audit(job_id)

    async with TestSessionLocal() as db:
        job = await db.get(AuditJob, job_id)
    assert job.status == AuditStatus.completed, (job.tier1_result, job.tier3_result, job.tier5_result)
    assert (job.tier1_status, job.tier2_status, job.tier3_status, job.tier4_status, job.tier5_status) == ("completed", "skipped", "completed", "completed", "completed")
    assert job.critical_count == 1 and job.high_count >= 3 and job.risk_score > 0
    assert job.total_pages_audited == job.tier1_result["files_scanned"] > 0
    assert job.tier3_result["dependencies"]["status"] == "checked"
    assert job.tier3_result["findings"][0]["id"] == "C-001"
    # No AI key: basic cases from the route list, and the result says so.
    assert job.total_test_cases > 0 and "AI service" in job.tier4_result["note"]
    assert "Files read" in job.executive_summary
    assert not archive.exists() and job.source_path is None        # the customer's code is not kept
    assert sorted(job.exports) == ["report", "results", "test-cases"]

    r = await client.get(f"/api/v1/audits/{job_id}/export/results", headers=auth_headers)
    assert r.status_code == 200 and r.json()["code"]["qa_gaps"]["untested_route_count"] == 1 and r.json()["web"] is None
    summary = (await client.get("/api/v1/dashboard/summary", headers=auth_headers)).json()
    assert summary["qa_gaps"] == 1


async def test_code_scan_fails_cleanly_on_a_bad_archive(test_user, storage, monkeypatch):
    monkeypatch.setattr(audit_orchestrator, "AsyncSessionLocal", TestSessionLocal)
    archive = storage / "upload.zip"
    archive.write_bytes(b"not a zip")
    async with TestSessionLocal() as db:
        job = AuditJob(created_by=test_user.id, source_type="code", source_path=str(archive), outputs=["security"])
        db.add(job)
        await db.commit()
        job_id = job.id
    await audit_orchestrator.run_audit(job_id)
    async with TestSessionLocal() as db:
        job = await db.get(AuditJob, job_id)
    assert job.status == AuditStatus.failed and "not a valid .zip" in job.tier1_result["error"]
    assert not archive.exists()
