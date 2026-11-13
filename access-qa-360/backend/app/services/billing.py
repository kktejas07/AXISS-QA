"""
Plans, and subscriptions through Stripe (US dollars) and Razorpay (rupees).

The providers host the payment pages; card details never reach this app. A
subscription becomes active only when the provider's signed webhook says so.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.models.organization import Organization
from app.services.orgs import DEFAULT_SEATS


class BillingError(Exception):
    """A problem to show the user in plain words."""


def providers() -> dict[str, bool]:
    return {
        "stripe": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET),
        "razorpay": bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET and settings.RAZORPAY_WEBHOOK_SECRET),
    }


def plans() -> list[dict]:
    """What the pricing page shows. Amounts come from settings so they can change without a release."""
    free = settings.FREE_SCANS_PER_MONTH
    return [
        {
            "id": "individual", "name": "Individual", "price_usd": 0, "price_inr": 0, "per": None,
            "summary": "For trying Wiseflow on your own apps.",
            "features": ["1 person", f"{free} scans a month" if free else "No limit on scans", "Web, mobile and source code scans", "Reports and test cases to download"],
        },
        {
            "id": "team", "name": "Team", "price_usd": settings.TEAM_PRICE_USD, "price_inr": settings.TEAM_PRICE_INR, "per": "per person, per month",
            "summary": "For teams that test together.",
            "features": ["As many people as you pay for", "No limit on scans", "Roles: owner, admin, member, viewer", "API keys for build pipelines", "Jira integration"],
        },
        {
            "id": "enterprise", "name": "Enterprise", "price_usd": None, "price_inr": None, "per": None,
            "summary": "For larger organisations with their own terms.",
            "features": ["No limit on people or scans", "Limits and terms agreed with you", "Invoicing instead of a card", "A named contact at Wiseflow"],
        },
    ]


# ---- applying a subscription's state to an organisation -----------------------

def activate(org: Organization, provider: str, subscription_id: str, seats: int, customer_id: str | None = None, period_end: datetime | None = None) -> None:
    org.billing_provider, org.billing_subscription_id, org.billing_status = provider, subscription_id, "active"
    org.billing_seats = seats
    org.billing_cancel_at_period_end = False
    if customer_id:
        org.billing_customer_id = customer_id
    if period_end:
        org.billing_period_end = period_end
    org.account_type = "team"
    org.seat_limit = seats
    org.scan_limit = None


def end(org: Organization) -> None:
    """The subscription is over. Members and results stay; new scans are refused until it is renewed."""
    org.billing_status = "cancelled"
    org.billing_cancel_at_period_end = False


def _when(unix: int | None) -> datetime | None:
    return datetime.fromtimestamp(unix, tz=timezone.utc) if unix else None


# ---- Stripe -------------------------------------------------------------------

_STRIPE = "https://api.stripe.com/v1"


async def _stripe(method: str, path: str, data: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.request(method, f"{_STRIPE}{path}", data=data, headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"})
    except httpx.HTTPError:
        raise BillingError("The payment provider could not be reached. Try again in a minute.")
    if r.status_code >= 400:
        raise BillingError("The payment provider refused the request. Try again, or contact support if it keeps happening.")
    return r.json()


async def stripe_checkout(org: Organization, email: str, seats: int) -> str:
    """Create a hosted checkout page for a monthly Team subscription. Returns its address."""
    base = settings.APP_URL.rstrip("/")
    session = await _stripe("POST", "/checkout/sessions", {
        "mode": "subscription",
        "success_url": f"{base}/settings?billing=success",
        "cancel_url": f"{base}/settings?billing=cancelled",
        "client_reference_id": org.id,
        "customer_email": email,
        "line_items[0][quantity]": seats,
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": settings.TEAM_PRICE_USD * 100,
        "line_items[0][price_data][recurring][interval]": "month",
        "line_items[0][price_data][product_data][name]": "Wiseflow Team, per person",
        "metadata[organization_id]": org.id,
        "metadata[seats]": seats,
        "subscription_data[metadata][organization_id]": org.id,
    })
    return session["url"]


async def stripe_portal(org: Organization) -> str:
    """Stripe's own page for changing the card, the number of seats, or cancelling."""
    session = await _stripe("POST", "/billing_portal/sessions", {"customer": org.billing_customer_id, "return_url": f"{settings.APP_URL.rstrip('/')}/settings"})
    return session["url"]


def verify_stripe(payload: bytes, header: str, tolerance: int = 300) -> bool:
    parts = dict(p.split("=", 1) for p in (header or "").split(",") if "=" in p)
    stamp, given = parts.get("t", ""), parts.get("v1", "")
    if not stamp.isdigit() or abs(time.time() - int(stamp)) > tolerance:
        return False
    expected = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, given)


# ---- Razorpay -----------------------------------------------------------------

_RAZORPAY = "https://api.razorpay.com/v1"
_plan_ids: dict[int, str] = {}   # rupee amount -> Razorpay plan id, so a plan is created once per price


async def _razorpay(method: str, path: str, body: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30, auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)) as client:
            r = await client.request(method, f"{_RAZORPAY}{path}", json=body)
    except httpx.HTTPError:
        raise BillingError("The payment provider could not be reached. Try again in a minute.")
    if r.status_code >= 400:
        raise BillingError("The payment provider refused the request. Try again, or contact support if it keeps happening.")
    return r.json()


async def razorpay_checkout(org: Organization, seats: int) -> tuple[str, str]:
    """Create a monthly subscription and return (its id, the hosted page where it is paid for)."""
    price = settings.TEAM_PRICE_INR
    if price not in _plan_ids:
        plan = await _razorpay("POST", "/plans", {"period": "monthly", "interval": 1, "item": {"name": "Wiseflow Team, per person", "amount": price * 100, "currency": "INR"}})
        _plan_ids[price] = plan["id"]
    sub = await _razorpay("POST", "/subscriptions", {
        "plan_id": _plan_ids[price], "total_count": 120, "quantity": seats, "customer_notify": 1,
        "notes": {"organization_id": org.id, "seats": str(seats)},
    })
    return sub["id"], sub["short_url"]


async def razorpay_cancel(org: Organization) -> None:
    await _razorpay("POST", f"/subscriptions/{org.billing_subscription_id}/cancel", {"cancel_at_cycle_end": 1})


def verify_razorpay(payload: bytes, signature: str) -> bool:
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def default_seats() -> int:
    return DEFAULT_SEATS["team"] or 10
