"""
Create a super admin and a few users to try the product with.

    python -m app.seed_accounts --domain example.com
    python -m app.seed_accounts --domain example.com --reset      # give the same accounts new passwords

Makes five accounts and prints each one's email and password once:

    admin@<domain>      super admin, in their own workspace
    owner@<domain>      owner of a Team organisation called "Demo team"
    member@<domain>     member of that organisation (can run scans)
    viewer@<domain>     viewer in that organisation (can only read)
    solo@<domain>       on their own, on the free Individual plan

Passwords are made at random each time and are never stored anywhere but the
database (hashed), so copy them when they are printed. Running it again leaves
existing accounts alone unless --reset is given. Use a domain you own, so that
password-reset emails cannot go to somebody else.
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import ROLE_SUPER_ADMIN, ROLE_USER, User
from app.services.orgs import DEFAULT_SEATS, create_personal_org

PEOPLE = [
    # (address before the @, name, platform role, organisation, role in it)
    ("admin", "Ada Admin", ROLE_SUPER_ADMIN, None, "owner"),
    ("owner", "Omar Owner", ROLE_USER, "Demo team", "owner"),
    ("member", "Mei Member", ROLE_USER, "Demo team", "member"),
    ("viewer", "Vik Viewer", ROLE_USER, "Demo team", "viewer"),
    ("solo", "Sam Solo", ROLE_USER, None, "owner"),
]
ABOUT = {"admin": "Super admin: the admin console and their own workspace", "owner": "Owner of the Team organisation \"Demo team\"",
         "member": "Member of \"Demo team\": can run scans", "viewer": "Viewer in \"Demo team\": can read, cannot run scans",
         "solo": "On their own, on the free Individual plan"}


def new_password() -> str:
    """Twenty characters that are easy to copy: no symbols a shell or a form might mangle."""
    return secrets.token_urlsafe(15)


async def seed(db, domain: str, reset: bool = False) -> list[dict]:
    """Create the accounts that are missing. Returns one row per account; `password` is None where an existing account was left alone."""
    domain = domain.strip().lower().lstrip("@")
    if "." not in domain or " " in domain or "/" in domain:
        raise ValueError("Give a domain such as example.com")
    team: Organization | None = None
    out = []
    for local, name, role, org_name, org_role in PEOPLE:
        email = f"{local}@{domain}"
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        password = None
        if user is None:
            password = new_password()
            user = User(email=email, full_name=name, hashed_password=get_password_hash(password), role=role)
            db.add(user)
            await db.flush()
            if org_name:
                if team is None:
                    team = (await db.execute(select(Organization).where(Organization.name == org_name))).scalars().first()
                if team is None:
                    team = Organization(name=org_name, account_type="team", seat_limit=DEFAULT_SEATS["team"], scan_limit=None)
                    db.add(team)
                    await db.flush()
                user.organization_id, user.org_role = team.id, org_role
            else:
                await create_personal_org(db, user)
        elif reset:
            password = new_password()
            user.hashed_password = get_password_hash(password)
            user.password_changed_at = datetime.now(timezone.utc)          # signs out anything using the old password
        await db.flush()
        out.append({"email": email, "password": password, "about": ABOUT[local]})
    return out


async def _main(domain: str, reset: bool) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = await seed(db, domain, reset)
        await db.commit()
    print(f"\nAccounts at {settings.APP_URL}/login\n")
    for row in rows:
        shown = row["password"] or "(already existed; password unchanged. Run again with --reset for a new one)"
        print(f"  {row['email']}\n    password: {shown}\n    {row['about']}\n")
    if any(r["password"] for r in rows):
        print("Copy these now: the passwords are not shown again. Each person can change theirs under Settings.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a super admin and a few users to try the product with.")
    parser.add_argument("--domain", required=True, help="a domain you own, such as example.com; the accounts are admin@, owner@, member@, viewer@ and solo@ it")
    parser.add_argument("--reset", action="store_true", help="give accounts that already exist a new password")
    args = parser.parse_args()
    asyncio.run(_main(args.domain, args.reset))
