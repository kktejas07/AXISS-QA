"""The signed-in user's organisation: details, members, roles and invitations.

Who may do what is decided by PERMISSIONS in app/services/orgs.py:
owners and admins manage the team; members run scans; viewers only look.
"""
import secrets
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.database import get_db
from app.models.organization import Invite, Organization
from app.models.user import User
from app.services.orgs import (
    by_seniority,
    create_personal_org,
    member_count,
    pending_invite_count,
    permissions_for,
    scans_this_month,
)

router = APIRouter(tags=["organisation"])


class OrgOut(BaseModel):
    id: str
    name: str
    account_type: str
    status: str
    seat_limit: int | None
    scan_limit: int | None
    seats_used: int
    pending_invites: int
    scans_this_month: int
    my_role: str
    permissions: list[str]


class OrgUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MemberOut(BaseModel):
    id: str
    full_name: str
    email: str
    org_role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberUpdate(BaseModel):
    role: Literal["owner", "admin", "member", "viewer"]


class InviteCreate(BaseModel):
    email: EmailStr
    role: Literal["admin", "member", "viewer"] = "member"


class InviteOut(BaseModel):
    id: str
    email: str
    role: str
    token: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitePreview(BaseModel):
    organization_name: str
    email: str
    role: str


async def _org_out(db: AsyncSession, ctx: OrgContext) -> OrgOut:
    org = ctx.org
    return OrgOut(
        id=org.id,
        name=org.name,
        account_type=org.account_type,
        status=org.status,
        seat_limit=org.seat_limit,
        scan_limit=org.scan_limit,
        seats_used=await member_count(db, org.id),
        pending_invites=await pending_invite_count(db, org.id),
        scans_this_month=await scans_this_month(db, org.id),
        my_role=ctx.role,
        permissions=permissions_for(ctx.role),
    )


async def _member(db: AsyncSession, ctx: OrgContext, user_id: str) -> User:
    member = (
        await db.execute(select(User).where(User.id == user_id, User.organization_id == ctx.org.id))
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(404, "That person is not in your organisation")
    return member


@router.get("/org", response_model=OrgOut)
async def get_org(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    return await _org_out(db, ctx)


@router.patch("/org", response_model=OrgOut)
async def update_org(body: OrgUpdate, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("org.edit")
    ctx.org.name = body.name.strip()
    await db.flush()
    return await _org_out(db, ctx)


@router.get("/org/members", response_model=list[MemberOut])
async def list_members(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    rows = await db.execute(select(User).where(User.organization_id == ctx.org.id))
    return by_seniority(list(rows.scalars().all()))


@router.patch("/org/members/{user_id}", response_model=MemberOut)
async def change_member_role(
    user_id: str, body: MemberUpdate, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)
):
    ctx.require("members.manage")
    member = await _member(db, ctx, user_id)
    if member.id == ctx.user.id:
        raise HTTPException(400, "You cannot change your own role. Ask another owner or admin.")
    # Only the owner may hand over ownership or change another owner.
    if (member.org_role == "owner" or body.role == "owner") and ctx.role != "owner":
        raise HTTPException(403, "Only the owner can transfer ownership")

    if body.role == "owner":
        # One owner per organisation: the previous owner steps down to admin.
        ctx.user.org_role = "admin"
    member.org_role = body.role
    await db.flush()
    return member


@router.delete("/org/members/{user_id}", status_code=204)
async def remove_member(user_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("members.manage")
    member = await _member(db, ctx, user_id)
    if member.id == ctx.user.id:
        raise HTTPException(400, "You cannot remove yourself")
    if member.org_role == "owner":
        raise HTTPException(403, "The owner cannot be removed. Transfer ownership first.")
    # They keep their account but lose access to this organisation's scans.
    await create_personal_org(db, member)


@router.get("/org/invites", response_model=list[InviteOut])
async def list_invites(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("members.manage")
    rows = await db.execute(
        select(Invite).where(Invite.organization_id == ctx.org.id, Invite.accepted_at.is_(None)).order_by(Invite.created_at.desc())
    )
    return rows.scalars().all()


@router.post("/org/invites", response_model=InviteOut, status_code=201)
async def create_invite(body: InviteCreate, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Create an invitation link. No email is sent: the inviter shares the link."""
    ctx.require("members.manage")
    org = ctx.org
    if org.account_type == "individual":
        raise HTTPException(403, "Individual accounts have one seat. Move to a Team account to invite people.")
    email = body.email.lower()

    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(409, "That email already has a Wiseflow account")
    duplicate = await db.execute(
        select(Invite).where(Invite.organization_id == org.id, Invite.email == email, Invite.accepted_at.is_(None))
    )
    if duplicate.scalar_one_or_none():
        raise HTTPException(409, "That email already has a pending invitation")
    if org.seat_limit is not None:
        used = await member_count(db, org.id) + await pending_invite_count(db, org.id)
        if used >= org.seat_limit:
            raise HTTPException(403, f"All {org.seat_limit} seats are in use. Remove someone or ask for more seats.")

    invite = Invite(organization_id=org.id, email=email, role=body.role, token=secrets.token_urlsafe(32), invited_by=ctx.user.id)
    db.add(invite)
    await db.flush()
    await db.refresh(invite)
    return invite


@router.delete("/org/invites/{invite_id}", status_code=204)
async def cancel_invite(invite_id: str, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    ctx.require("members.manage")
    invite = (
        await db.execute(select(Invite).where(Invite.id == invite_id, Invite.organization_id == ctx.org.id, Invite.accepted_at.is_(None)))
    ).scalar_one_or_none()
    if not invite:
        raise HTTPException(404, "Invitation not found")
    await db.delete(invite)


@router.get("/invites/{token}", response_model=InvitePreview)
async def preview_invite(token: str, db: AsyncSession = Depends(get_db)):
    """Public: what an invitation link is for, shown on the sign-up page."""
    invite = (await db.execute(select(Invite).where(Invite.token == token, Invite.accepted_at.is_(None)))).scalar_one_or_none()
    if not invite:
        raise HTTPException(404, "This invitation is no longer valid")
    org = await db.get(Organization, invite.organization_id)
    return InvitePreview(organization_name=org.name, email=invite.email, role=invite.role)
