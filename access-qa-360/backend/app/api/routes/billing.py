"""
Plans and subscriptions.

GET  /api/v1/billing/plans                 public: what the pricing page shows
GET  /api/v1/billing                       this organisation's plan and subscription
POST /api/v1/billing/checkout              owner: start paying for the Team plan
POST /api/v1/billing/manage                owner: Stripe's page for card, seats and cancelling
POST /api/v1/billing/cancel                owner: cancel a Razorpay subscription at the end of the period
POST /api/v1/billing/webhooks/stripe       signed by Stripe
POST /api/v1/billing/webhooks/razorpay     signed by Razorpay
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import OrgContext, get_org_context
from app.core.config import settings
from app.core.database import get_db
from app.models.organization import Organization
from app.services import billing
from app.services.orgs import member_count, pending_invite_count

router = APIRouter(prefix="/billing", tags=["billing"])


class BillingOut(BaseModel):
    account_type: str
    seat_limit: int | None
    seats_used: int
    provider: str | None
    status: str | None
    seats: int | None
    period_end: datetime | None
    cancel_at_period_end: bool
    # Which providers this server can take payment through.
    providers: dict[str, bool]
    can_manage: bool


class CheckoutIn(BaseModel):
    provider: Literal["stripe", "razorpay"]
    seats: int = Field(ge=1, le=500)


def _owner(ctx: OrgContext) -> None:
    if ctx.via_api_key or ctx.role != "owner":
        raise HTTPException(403, "Only the organisation's owner can change billing")


@router.get("/plans")
async def list_plans():
    return {"plans": billing.plans(), "providers": billing.providers(), "sales_email": settings.SALES_EMAIL or None}


@router.get("", response_model=BillingOut)
async def get_billing(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    org = ctx.org
    return BillingOut(
        account_type=org.account_type, seat_limit=org.seat_limit, seats_used=await member_count(db, org.id),
        provider=org.billing_provider, status=org.billing_status, seats=org.billing_seats, period_end=org.billing_period_end,
        cancel_at_period_end=org.billing_cancel_at_period_end, providers=billing.providers(),
        can_manage=ctx.role == "owner" and not ctx.via_api_key,
    )


@router.post("/checkout")
async def checkout(body: CheckoutIn, db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Send the owner to the provider's payment page. Nothing changes here until the provider confirms payment."""
    _owner(ctx)
    org = ctx.org
    if org.billing_status in ("active", "past_due"):
        raise HTTPException(409, "This organisation already has a subscription. Use Manage subscription to change it.")
    if org.account_type == "enterprise":
        raise HTTPException(409, "Enterprise accounts are invoiced. Contact Wiseflow to change yours.")
    if not billing.providers()[body.provider]:
        raise HTTPException(400, "That payment method is not available on this server")
    people = await member_count(db, org.id) + await pending_invite_count(db, org.id)
    if body.seats < people:
        raise HTTPException(400, f"Your organisation has {people} people including pending invitations, so it needs at least {people} seats.")
    try:
        if body.provider == "stripe":
            return {"url": await billing.stripe_checkout(org, ctx.user.email, body.seats)}
        subscription_id, url = await billing.razorpay_checkout(org, body.seats)
    except billing.BillingError as e:
        raise HTTPException(502, str(e))
    # Remember which subscription is being paid for, so the webhook can be matched to this organisation.
    org.billing_provider, org.billing_subscription_id, org.billing_seats = "razorpay", subscription_id, body.seats
    return {"url": url}


@router.post("/manage")
async def manage(ctx: OrgContext = Depends(get_org_context)):
    _owner(ctx)
    org = ctx.org
    if org.billing_provider != "stripe" or not org.billing_customer_id:
        raise HTTPException(400, "This subscription is not managed through Stripe")
    try:
        return {"url": await billing.stripe_portal(org)}
    except billing.BillingError as e:
        raise HTTPException(502, str(e))


@router.post("/cancel", response_model=BillingOut)
async def cancel(db: AsyncSession = Depends(get_db), ctx: OrgContext = Depends(get_org_context)):
    """Razorpay only: stop renewing. The plan stays active until the period already paid for ends."""
    _owner(ctx)
    org = ctx.org
    if org.billing_provider != "razorpay" or org.billing_status != "active":
        raise HTTPException(400, "There is no active Razorpay subscription to cancel")
    try:
        await billing.razorpay_cancel(org)
    except billing.BillingError as e:
        raise HTTPException(502, str(e))
    org.billing_cancel_at_period_end = True
    await db.flush()
    return await get_billing(db, ctx)


# ---- webhooks -----------------------------------------------------------------

async def _org_for(db: AsyncSession, organization_id: str | None, subscription_id: str | None) -> Organization | None:
    if organization_id:
        org = await db.get(Organization, organization_id)
        if org:
            return org
    if subscription_id:
        return (await db.execute(select(Organization).where(Organization.billing_subscription_id == subscription_id))).scalar_one_or_none()
    return None


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    if not settings.STRIPE_WEBHOOK_SECRET or not billing.verify_stripe(payload, request.headers.get("stripe-signature", "")):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(payload)
    kind, obj = event.get("type", ""), (event.get("data") or {}).get("object") or {}
    meta = obj.get("metadata") or {}

    if kind == "checkout.session.completed" and obj.get("subscription"):
        org = await _org_for(db, obj.get("client_reference_id") or meta.get("organization_id"), None)
        if org:
            billing.activate(org, "stripe", obj["subscription"], int(meta.get("seats") or org.billing_seats or 1), customer_id=obj.get("customer"))
    elif kind in ("customer.subscription.updated", "customer.subscription.deleted"):
        org = await _org_for(db, meta.get("organization_id"), obj.get("id"))
        if org and org.billing_subscription_id in (None, obj.get("id")):
            status = obj.get("status")
            item = ((obj.get("items") or {}).get("data") or [{}])[0]
            if kind.endswith("deleted") or status in ("canceled", "unpaid", "incomplete_expired"):
                billing.end(org)
            else:
                seats = int(item.get("quantity") or org.billing_seats or 1)
                billing.activate(org, "stripe", obj["id"], seats, customer_id=obj.get("customer"),
                                 period_end=billing._when(obj.get("current_period_end") or item.get("current_period_end")))
                org.billing_status = "past_due" if status == "past_due" else "active"
                org.billing_cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    elif kind == "invoice.payment_failed":
        subscription_id = obj.get("subscription") or (((obj.get("parent") or {}).get("subscription_details") or {}).get("subscription"))
        org = await _org_for(db, None, subscription_id)
        if org and org.billing_status == "active":
            org.billing_status = "past_due"
    return {"received": True}


@router.post("/webhooks/razorpay", include_in_schema=False)
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    if not settings.RAZORPAY_WEBHOOK_SECRET or not billing.verify_razorpay(payload, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(payload)
    kind = event.get("event", "")
    sub = (((event.get("payload") or {}).get("subscription") or {}).get("entity")) or {}
    notes = sub.get("notes") if isinstance(sub.get("notes"), dict) else {}
    org = await _org_for(db, notes.get("organization_id"), sub.get("id"))
    if not org or (org.billing_subscription_id and org.billing_subscription_id != sub.get("id")):
        return {"received": True}

    if kind in ("subscription.activated", "subscription.charged"):
        keep_cancel = org.billing_cancel_at_period_end
        billing.activate(org, "razorpay", sub["id"], int(sub.get("quantity") or org.billing_seats or 1),
                         customer_id=sub.get("customer_id"), period_end=billing._when(sub.get("current_end")))
        org.billing_cancel_at_period_end = keep_cancel
    elif kind in ("subscription.pending", "subscription.halted"):
        org.billing_status = "past_due"
    elif kind in ("subscription.cancelled", "subscription.completed", "subscription.expired"):
        billing.end(org)
    return {"received": True}
