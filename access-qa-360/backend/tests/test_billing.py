"""Plans, checkout and the signed webhooks from Stripe and Razorpay."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

import pytest
from httpx import AsyncClient

from app.api.routes import audits as audits_routes
from app.core.config import settings
from app.models.organization import Organization
from app.models.user import User
from app.services import billing
from tests.conftest import TestSessionLocal

API = "/api/v1/billing"


@pytest.fixture
def paid(monkeypatch):
    """Both providers switched on with test secrets."""
    for key, value in (("STRIPE_SECRET_KEY", "sk_test_x"), ("STRIPE_WEBHOOK_SECRET", "whsec_x"), ("RAZORPAY_KEY_ID", "rzp_test_x"),
                       ("RAZORPAY_KEY_SECRET", "rzp_secret"), ("RAZORPAY_WEBHOOK_SECRET", "rzp_hook"), ("APP_URL", "https://app.example.com")):
        monkeypatch.setattr(settings, key, value)
    billing._plan_ids.clear()


async def _org(client: AsyncClient, headers) -> str:
    return (await client.get("/api/v1/auth/me", headers=headers)).json()["organization_id"]


async def _state(org_id: str) -> Organization:
    async with TestSessionLocal() as db:
        return await db.get(Organization, org_id)


def stripe_event(kind: str, obj: dict, secret: str = "whsec_x", stamp: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps({"type": kind, "data": {"object": obj}}).encode()
    stamp = stamp or int(time.time())
    sig = hmac.new(secret.encode(), f"{stamp}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={stamp},v1={sig}", "content-type": "application/json"}


def razorpay_event(kind: str, sub: dict, secret: str = "rzp_hook") -> tuple[bytes, dict]:
    body = json.dumps({"event": kind, "payload": {"subscription": {"entity": sub}}}).encode()
    return body, {"x-razorpay-signature": hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), "content-type": "application/json"}


async def test_plans_are_public_and_use_the_configured_prices(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "TEAM_PRICE_USD", 35)
    data = (await client.get(f"{API}/plans")).json()
    assert [p["id"] for p in data["plans"]] == ["individual", "team", "enterprise"]
    assert data["plans"][1]["price_usd"] == 35 and data["plans"][2]["price_usd"] is None
    assert data["providers"] == {"stripe": False, "razorpay": False}


async def test_new_accounts_get_the_free_plan_allowance(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "FREE_SCANS_PER_MONTH", 2)
    monkeypatch.setattr(audits_routes, "_launch", lambda job_id: None)
    await client.post("/api/v1/auth/register", json={"email": "new@acme.io", "password": "demo-pass-1", "full_name": "New Person"})
    token = (await client.post("/api/v1/auth/login", json={"email": "new@acme.io", "password": "demo-pass-1"})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    codes = [(await client.post("/api/v1/audits", headers=headers, json={"target_url": "https://shop.example.com"})).status_code for _ in range(3)]
    assert codes == [201, 201, 403]


async def test_stripe_checkout_then_webhooks_drive_the_subscription(client: AsyncClient, test_user, auth_headers, paid, httpx_mock, monkeypatch):
    monkeypatch.setattr(audits_routes, "_launch", lambda job_id: None)
    org_id = await _org(client, auth_headers)
    httpx_mock.add_response(url="https://api.stripe.com/v1/checkout/sessions", method="POST", json={"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"})

    r = await client.post(f"{API}/checkout", headers=auth_headers, json={"provider": "stripe", "seats": 5})
    assert r.status_code == 200 and r.json() == {"url": "https://checkout.stripe.com/c/pay/cs_1"}
    sent = parse_qs(httpx_mock.get_requests()[0].content.decode())
    assert sent["mode"] == ["subscription"] and sent["line_items[0][quantity]"] == ["5"]
    assert sent["line_items[0][price_data][unit_amount]"] == [str(settings.TEAM_PRICE_USD * 100)] and sent["client_reference_id"] == [org_id]
    assert sent["success_url"] == ["https://app.example.com/settings?billing=success"]
    # Nothing is unlocked until Stripe confirms payment.
    assert (await _state(org_id)).account_type == "individual"

    # A forged or stale webhook is refused.
    body, headers = stripe_event("checkout.session.completed", {"client_reference_id": org_id, "subscription": "sub_1", "customer": "cus_1", "metadata": {"seats": "5"}}, secret="wrong")
    assert (await client.post(f"{API}/webhooks/stripe", content=body, headers=headers)).status_code == 400
    body, headers = stripe_event("checkout.session.completed", {"client_reference_id": org_id, "subscription": "sub_1"}, stamp=int(time.time()) - 3600)
    assert (await client.post(f"{API}/webhooks/stripe", content=body, headers=headers)).status_code == 400
    assert (await _state(org_id)).billing_status is None

    body, headers = stripe_event("checkout.session.completed", {"client_reference_id": org_id, "subscription": "sub_1", "customer": "cus_1", "metadata": {"seats": "5"}})
    assert (await client.post(f"{API}/webhooks/stripe", content=body, headers=headers)).status_code == 200
    org = await _state(org_id)
    assert (org.account_type, org.seat_limit, org.scan_limit, org.billing_status, org.billing_provider, org.billing_customer_id) == ("team", 5, None, "active", "stripe", "cus_1")
    mine = (await client.get(API, headers=auth_headers)).json()
    assert mine["status"] == "active" and mine["seats"] == 5 and mine["can_manage"] is True
    assert (await client.post(f"{API}/checkout", headers=auth_headers, json={"provider": "stripe", "seats": 5})).status_code == 409

    # Seats changed in Stripe's portal, then a failed payment, then the subscription ends.
    body, headers = stripe_event("customer.subscription.updated", {"id": "sub_1", "status": "active", "customer": "cus_1", "current_period_end": 1900000000, "cancel_at_period_end": True, "items": {"data": [{"quantity": 8}]}})
    await client.post(f"{API}/webhooks/stripe", content=body, headers=headers)
    org = await _state(org_id)
    assert org.seat_limit == 8 and org.billing_cancel_at_period_end is True and org.billing_period_end.year == 2030

    body, headers = stripe_event("invoice.payment_failed", {"subscription": "sub_1"})
    await client.post(f"{API}/webhooks/stripe", content=body, headers=headers)
    assert (await _state(org_id)).billing_status == "past_due"
    assert (await client.post("/api/v1/audits", headers=auth_headers, json={"target_url": "https://shop.example.com"})).status_code == 201   # still allowed while payment is retried

    body, headers = stripe_event("customer.subscription.deleted", {"id": "sub_1", "status": "canceled"})
    await client.post(f"{API}/webhooks/stripe", content=body, headers=headers)
    assert (await _state(org_id)).billing_status == "cancelled"
    blocked = await client.post("/api/v1/audits", headers=auth_headers, json={"target_url": "https://shop.example.com"})
    assert blocked.status_code == 403 and "subscription has ended" in blocked.json()["detail"]


async def test_razorpay_checkout_webhook_and_cancel(client: AsyncClient, test_user, auth_headers, paid, httpx_mock):
    org_id = await _org(client, auth_headers)
    httpx_mock.add_response(url="https://api.razorpay.com/v1/plans", method="POST", json={"id": "plan_1"})
    httpx_mock.add_response(url="https://api.razorpay.com/v1/subscriptions", method="POST", json={"id": "sub_rzp_1", "status": "created", "short_url": "https://rzp.io/i/abc"})

    r = await client.post(f"{API}/checkout", headers=auth_headers, json={"provider": "razorpay", "seats": 3})
    assert r.status_code == 200 and r.json() == {"url": "https://rzp.io/i/abc"}
    plan, sub = (json.loads(q.content) for q in httpx_mock.get_requests())
    assert plan["item"] == {"name": "Wiseflow Team, per person", "amount": settings.TEAM_PRICE_INR * 100, "currency": "INR"}
    assert sub["plan_id"] == "plan_1" and sub["quantity"] == 3 and sub["notes"]["organization_id"] == org_id
    assert (await _state(org_id)).account_type == "individual"

    body, headers = razorpay_event("subscription.activated", {"id": "sub_rzp_1", "quantity": 3, "current_end": 1900000000, "notes": {"organization_id": org_id}}, secret="forged")
    assert (await client.post(f"{API}/webhooks/razorpay", content=body, headers=headers)).status_code == 400

    body, headers = razorpay_event("subscription.activated", {"id": "sub_rzp_1", "quantity": 3, "current_end": 1900000000, "notes": {"organization_id": org_id}})
    assert (await client.post(f"{API}/webhooks/razorpay", content=body, headers=headers)).status_code == 200
    org = await _state(org_id)
    assert (org.account_type, org.seat_limit, org.billing_status, org.billing_provider) == ("team", 3, "active", "razorpay")

    httpx_mock.add_response(url="https://api.razorpay.com/v1/subscriptions/sub_rzp_1/cancel", method="POST", json={"id": "sub_rzp_1", "status": "active"})
    cancelled = await client.post(f"{API}/cancel", headers=auth_headers)
    assert cancelled.status_code == 200 and cancelled.json()["cancel_at_period_end"] is True and cancelled.json()["status"] == "active"

    body, headers = razorpay_event("subscription.cancelled", {"id": "sub_rzp_1", "notes": {"organization_id": org_id}})
    await client.post(f"{API}/webhooks/razorpay", content=body, headers=headers)
    assert (await _state(org_id)).billing_status == "cancelled"


async def test_checkout_rules(client: AsyncClient, test_user, auth_headers, paid, monkeypatch):
    assert (await client.post(f"{API}/checkout", headers=auth_headers, json={"provider": "stripe", "seats": 0})).status_code == 422
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    off = await client.post(f"{API}/checkout", headers=auth_headers, json={"provider": "stripe", "seats": 2})
    assert off.status_code == 400 and "not available" in off.json()["detail"]

    # Only the owner may change billing.
    async with TestSessionLocal() as db:
        (await db.get(User, test_user.id)).org_role = "admin"
        await db.commit()
    assert (await client.post(f"{API}/checkout", headers=auth_headers, json={"provider": "razorpay", "seats": 2})).status_code == 403
    assert (await client.get(API, headers=auth_headers)).json()["can_manage"] is False
