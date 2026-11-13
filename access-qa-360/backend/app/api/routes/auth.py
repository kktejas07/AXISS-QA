from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.models.user import User, ROLE_SUPER_ADMIN, ROLE_USER
from datetime import datetime, timezone

from app.models.organization import Invite, Organization
from app.schemas.auth import (
    Token, LoginRequest, RegisterRequest, UserOut, MeOut, OrgBrief,
    ForgotPasswordRequest, ForgotPasswordOut, ResetPasswordRequest, ChangePasswordRequest,
)
from app.services import password_reset
from app.services.mailer import email_configured, send_email
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


@router.post("/forgot-password", response_model=ForgotPasswordOut)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Email a reset link. The answer is the same whether or not the address has an
    account, so this cannot be used to find out who is registered.
    """
    if not email_configured():
        return ForgotPasswordOut(delivery="admin")
    user = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if user and user.is_active and await password_reset.recent_link_count(db, user.id) < password_reset.MAX_LINKS_PER_HOUR:
        token, _ = await password_reset.create_reset(db, user)
        await db.commit()
        await send_email(
            user.email,
            "Reset your Wiseflow password",
            f"Hello {user.full_name},\n\nUse this link to choose a new password. It works once and expires in "
            f"{settings.PASSWORD_RESET_MINUTES} minutes.\n\n{password_reset.reset_url(token)}\n\n"
            "If you did not ask for this, ignore this email; your password stays as it is.\n",
        )
    return ForgotPasswordOut(delivery="email")


@router.get("/reset-password/{token}")
async def check_reset_link(token: str, db: AsyncSession = Depends(get_db)):
    """Public: whether a reset link still works, and which account it is for."""
    found = await password_reset.find_reset(db, token)
    if not found:
        raise HTTPException(status_code=404, detail="This reset link has expired or was already used")
    return {"email": found[1].email}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    found = await password_reset.find_reset(db, body.token)
    if not found:
        raise HTTPException(status_code=400, detail="This reset link has expired or was already used. Ask for a new one.")
    await password_reset.set_password(db, found[1], body.password)
    return {"email": found[1].email}


@router.post("/change-password", response_model=Token)
async def change_password(body: ChangePasswordRequest, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Change the signed-in user's password. Other devices are signed out; this one gets a fresh token."""
    if ctx.via_api_key:
        raise HTTPException(status_code=403, detail="API keys cannot change a password")
    user = ctx.user
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="The current password is not correct")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="Choose a password that is different from the current one")
    await password_reset.set_password(db, user, body.new_password)
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
