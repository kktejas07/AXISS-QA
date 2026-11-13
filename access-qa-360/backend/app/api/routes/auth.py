import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
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
from app.services import password_reset, sso, totp
from app.core.secrets import decrypt, encrypt
from pydantic import BaseModel
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
    if user.organization_id and not user.is_super_admin and user.org_role != "owner":
        org = await db.get(Organization, user.organization_id)
        if org and org.require_sso and sso.providers()["google"]:
            raise HTTPException(status_code=403, detail="Your organisation requires signing in with Google. Use “Continue with Google”.")
    if user.totp_enabled_at:
        if not body.code:
            # The sign-in page shows the code box when it sees this.
            raise HTTPException(status_code=401, detail="two_step_required")
        counter = totp.verify(decrypt(user.totp_secret_encrypted or "") or "", body.code, user.totp_last_counter)
        if counter is None:
            raise HTTPException(status_code=401, detail="That code is not right. Check your authenticator app and try again.")
        user.totp_last_counter = counter
    if not user.is_super_admin and _is_bootstrap_admin(user.email):
        user.role = ROLE_SUPER_ADMIN
    return Token(access_token=create_access_token(user.id))


# ---- two-step sign-in --------------------------------------------------------

class TwoStepCode(BaseModel):
    code: str


class TwoStepOff(BaseModel):
    password: str
    code: str


def _person(ctx: OrgContext) -> User:
    if ctx.via_api_key:
        raise HTTPException(status_code=403, detail="API keys cannot change sign-in settings")
    return ctx.user


@router.post("/2fa/setup")
async def two_step_setup(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Start setting up an authenticator app. Nothing changes until a code from it is confirmed."""
    user = _person(ctx)
    if user.totp_enabled_at:
        raise HTTPException(status_code=409, detail="Two-step sign-in is already on")
    secret = totp.new_secret()
    user.totp_secret_encrypted, user.totp_last_counter = encrypt(secret), None
    await db.flush()
    return {"secret": secret, "uri": totp.uri(secret, user.email)}


@router.post("/2fa/enable")
async def two_step_enable(body: TwoStepCode, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    user = _person(ctx)
    secret = decrypt(user.totp_secret_encrypted or "")
    if user.totp_enabled_at or not secret:
        raise HTTPException(status_code=400, detail="Start the setup again")
    counter = totp.verify(secret, body.code, None)
    if counter is None:
        raise HTTPException(status_code=400, detail="That code is not right. Check your authenticator app and try again.")
    user.totp_enabled_at, user.totp_last_counter = datetime.now(timezone.utc), counter
    await db.flush()
    return {"enabled": True}


@router.post("/2fa/disable")
async def two_step_disable(body: TwoStepOff, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    user = _person(ctx)
    if not user.totp_enabled_at:
        return {"enabled": False}
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="The password is not correct")
    if totp.verify(decrypt(user.totp_secret_encrypted or "") or "", body.code, user.totp_last_counter) is None:
        raise HTTPException(status_code=400, detail="That code is not right. Check your authenticator app and try again.")
    user.totp_secret_encrypted = user.totp_enabled_at = user.totp_last_counter = None
    await db.flush()
    return {"enabled": False}


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


# ---- sign in with Google ------------------------------------------

SSO_COOKIE = "wf_sso"


def _back_to_login(code: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.APP_URL.rstrip('/')}/login?sso_error={code}", status_code=302)


@router.get("/sso/providers")
async def sso_providers():
    return sso.providers()


@router.get("/sso/{provider}/start")
async def sso_start(provider: Literal["google"], invite: str | None = None):
    """Send the browser to the provider's sign-in page."""
    try:
        url, nonce = sso.authorize_url(provider, invite)
    except sso.SsoError as e:
        return _back_to_login(e.code)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(SSO_COOKIE, nonce, max_age=600, httponly=True, samesite="lax", secure=settings.APP_URL.startswith("https://"), path="/")
    return response


@router.get("/sso/{provider}/callback")
async def sso_callback(
    request: Request, provider: Literal["google"], code: str | None = None, state: str | None = None, error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """The provider sends the person back here. Sign them in, creating the account on first use."""
    if error or not code:
        return _back_to_login("cancelled")
    try:
        claims = sso.read_state(state or "", provider, request.cookies.get(SSO_COOKIE))
        if not sso.providers().get(provider):
            raise sso.SsoError("unavailable")
        email, name = await sso.identity(provider, code)
    except sso.SsoError as e:
        return _back_to_login(e.code)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user and not user.is_active:
        return _back_to_login("deactivated")
    if not user:
        invite = None
        if claims.get("i"):
            invite = (await db.execute(select(Invite).where(Invite.token == claims["i"], Invite.accepted_at.is_(None)))).scalar_one_or_none()
            if not invite or invite.email != email:
                return _back_to_login("invite_mismatch")
            org = await db.get(Organization, invite.organization_id)
            if org.seat_limit is not None and await member_count(db, org.id) >= org.seat_limit:
                return _back_to_login("no_seats")
        # No password is set; the person can add one later with "Forgot password".
        user = User(email=email, full_name=name, hashed_password=get_password_hash(secrets.token_urlsafe(32)),
                    role=ROLE_SUPER_ADMIN if _is_bootstrap_admin(email) else ROLE_USER)
        db.add(user)
        await db.flush()
        if invite:
            user.organization_id, user.org_role = invite.organization_id, invite.role
            invite.accepted_at = datetime.now(timezone.utc)
            await db.flush()
        else:
            await create_personal_org(db, user)
    elif not user.is_super_admin and _is_bootstrap_admin(user.email):
        user.role = ROLE_SUPER_ADMIN
    await db.commit()
    # In the address fragment, which browsers never send to a server or write to its logs.
    return RedirectResponse(f"{settings.APP_URL.rstrip('/')}/sso#token={create_access_token(user.id)}", status_code=302)


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
        two_step_enabled=bool(user.totp_enabled_at),
    )
