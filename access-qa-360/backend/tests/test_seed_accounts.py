"""The command that creates a super admin and a few users to try the product with."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.organization import Organization
from app.models.user import User
from app.seed_accounts import seed
from tests.conftest import TestSessionLocal

API = "/api/v1"


async def run(domain="demo.example", reset=False):
    async with TestSessionLocal() as db:
        rows = await seed(db, domain, reset)
        await db.commit()
    return {r["email"].split("@")[0]: r for r in rows}


async def sign_in(client, row):
    r = await client.post(f"{API}/auth/login", json={"email": row["email"], "password": row["password"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_it_makes_a_super_admin_a_team_and_a_solo_user_who_can_all_sign_in(client: AsyncClient):
    made = await run()
    assert set(made) == {"admin", "owner", "member", "viewer", "solo"} and all(len(r["password"]) >= 20 for r in made.values())
    assert len({r["password"] for r in made.values()}) == 5                                  # each account has its own

    admin = await sign_in(client, made["admin"])
    assert (await client.get(f"{API}/auth/me", headers=admin)).json()["role"] == "super_admin"
    assert (await client.get(f"{API}/admin/overview", headers=admin)).status_code == 200

    who = {name: (await client.get(f"{API}/auth/me", headers=await sign_in(client, made[name]))).json() for name in ("owner", "member", "viewer", "solo")}
    assert {who[n]["organization"]["name"] for n in ("owner", "member", "viewer")} == {"Demo team"}
    assert [(who[n]["org_role"], who[n]["organization"]["account_type"]) for n in ("owner", "member", "viewer")] == [("owner", "team"), ("member", "team"), ("viewer", "team")]
    assert who["solo"]["organization"]["account_type"] == "individual" and who["solo"]["role"] == "user"
    assert "scan.run" in who["member"]["permissions"] and "scan.run" not in who["viewer"]["permissions"]
    # A normal user is kept out of the admin console.
    assert (await client.get(f"{API}/admin/overview", headers=await sign_in(client, made["owner"]))).status_code == 403


async def test_running_it_again_changes_nothing_unless_asked_to_reset(client: AsyncClient):
    first = await run()
    again = await run()
    assert all(r["password"] is None for r in again.values())
    await sign_in(client, first["owner"])                                                    # the first password still works
    async with TestSessionLocal() as db:
        assert len((await db.execute(select(User))).scalars().all()) == 5
        assert len((await db.execute(select(Organization).where(Organization.name == "Demo team"))).scalars().all()) == 1

    new = await run(reset=True)
    assert new["owner"]["password"] and new["owner"]["password"] != first["owner"]["password"]
    assert (await client.post(f"{API}/auth/login", json={"email": first["owner"]["email"], "password": first["owner"]["password"]})).status_code in (400, 401)
    await sign_in(client, new["owner"])


async def test_it_refuses_something_that_is_not_a_domain():
    for bad in ("", "localhost", "not a domain.com", "example.com/x"):
        with pytest.raises(ValueError):
            async with TestSessionLocal() as db:
                await seed(db, bad)
