import httpx
import pytest

from app.services.api_auditor import probe_jwt


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_html_shell_is_not_reported_as_an_open_endpoint():
    """A single-page app returns 200 and HTML for any path; that is not a finding."""
    async with _client(lambda request: httpx.Response(200, html="<!doctype html><div id=root></div>")) as client:
        assert await probe_jwt("https://shop.example.com", None, client) == []


@pytest.mark.asyncio
async def test_json_without_a_token_is_reported():
    async with _client(lambda request: httpx.Response(200, json={"id": 1, "email": "a@shop.example.com"})) as client:
        findings = await probe_jwt("https://shop.example.com", None, client)
    assert [f.check for f in findings] == ["missing_auth"] and findings[0].severity == "critical"


@pytest.mark.asyncio
async def test_protected_endpoint_is_clean():
    async with _client(lambda request: httpx.Response(401, json={"detail": "Not authenticated"})) as client:
        assert await probe_jwt("https://shop.example.com", None, client) == []
