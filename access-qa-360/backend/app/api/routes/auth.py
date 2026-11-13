from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.models.user import User, ROLE_SUPER_ADMIN, ROLE_USER
from datetime import datetime, timezone

from app.models.organization import Invite, Organization
from app.schemas.auth import Token, LoginRequest, RegisterRequest, UserOut, MeOut, OrgBrief
from app.api.deps import OrgContext, get_org_context
from app.services.orgs import create_personal_org, member_count, permissions_for

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_bootstrap_admin(email: str) -> bool:
    """True when the email is listed in SUPER_ADMIN_EMAILS."""
    listed = {e.strip().lower() for e in settings.SUPER_ADMIN_EMAILS.split(",") if e.strip()}
    return email.lower() in listed


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = body.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    invite = None
    if body.invite_token:
        invite = (
            await db.execute(select(Invite).where(Invite.token == body.invite_token, Invite.accepted_at.is_(None)))
        ).scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=400, detail="This invitation is no longer valid")
        if invite.email != email:
            raise HTTPException(status_code=400, detail=f"This invitation is for {invite.email}. Sign up with that email.")
        org = await db.get(Organization, invite.organization_id)
        if org.seat_limit is not None and await member_count(db, org.id) >= org.seat_limit:
            raise HTTPException(status_code=403, detail="That organisation has no free seats. Ask its owner to make room.")

    user = User(
        email=email,
        full_name=body.full_name,
        hashed_password=get_password_hash(body.password),
        role=ROLE_SUPER_ADMIN if _is_bootstrap_admin(email) else ROLE_USER,
    )
    db.add(user)
    await db.flush()

    if invite:
        user.organization_id = invite.organization_id
        user.org_role = invite.role
        invite.accepted_at = datetime.now(timezone.utc)
        await db.flush()
    else:
        await create_personal_org(db, user)
    return user


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    if not user.is_super_admin and _is_bootstrap_admin(user.email):
        user.role = ROLE_SUPER_ADMIN
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=MeOut)
async def me(ctx: OrgContext = Depends(get_org_context)):
    user, org = ctx.user, ctx.org
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        role=user.role,
        organization_id=org.id,
        org_role=ctx.role,
        organization=OrgBrief(id=org.id, name=org.name, account_type=org.account_type, status=org.status),
        permissions=permissions_for(ctx.role),
    )
