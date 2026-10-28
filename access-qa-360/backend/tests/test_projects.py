import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, auth_headers):
    response = await client.post("/api/v1/projects", json={
        "name": "My App",
        "base_url": "https://example.com",
        "description": "Test project",
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My App"
    assert data["base_url"] == "https://example.com"


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, auth_headers):
    await client.post("/api/v1/projects", json={"name": "P1", "base_url": "https://p1.com"}, headers=auth_headers)
    await client.post("/api/v1/projects", json={"name": "P2", "base_url": "https://p2.com"}, headers=auth_headers)
    response = await client.get("/api/v1/projects", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 2


@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/projects")
    assert response.status_code == 403
