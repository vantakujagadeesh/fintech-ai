"""
POST /webhooks/stripe — Stripe webhook handler.
Updates user plan in DB on checkout.session.completed event.
"""

from __future__ import annotations

import logging

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.db import User, get_db

logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY

VALID_PLANS = {"free", "starter", "pro"}


class CheckoutSessionRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/billing/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for plan upgrade."""
    from backend.core.tenancy import get_current_tenant, get_redis
    import redis.asyncio as aioredis

    # Get tenant from Authorization header
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    tenant = await get_current_tenant(authorization=auth, db=db)

    if body.plan not in VALID_PLANS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {body.plan}")

    price_id = (
        settings.STRIPE_STARTER_PRICE_ID
        if body.plan == "starter"
        else settings.STRIPE_PRO_PRICE_ID
    )

    if not price_id:
        raise HTTPException(
            status_code=400,
            detail="Stripe price ID not configured. Contact support.",
        )

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            metadata={
                "tenant_id": tenant.tenant_id,
                "plan": body.plan,
            },
        )

        return CheckoutSessionResponse(
            checkout_url=session.url,
            session_id=session.id,
        )

    except stripe.error.StripeError as exc:
        logger.error(f"[Billing] Stripe error: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle Stripe webhook events.
    On checkout.session.completed → update user's plan in DB.
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("[Billing] Invalid Stripe webhook signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature",
        )
    except Exception as exc:
        logger.error(f"[Billing] Webhook parse error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))

    event_type = event["type"]
    logger.info(f"[Billing] Received Stripe event: {event_type}")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        await _handle_checkout_completed(session, db)

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        await _handle_subscription_cancelled(subscription, db)

    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        logger.warning(f"[Billing] Payment failed for customer: {invoice.get('customer')}")

    return {"received": True, "event_type": event_type}


async def _handle_checkout_completed(session: dict, db: AsyncSession) -> None:
    """Update user plan after successful checkout."""
    metadata = session.get("metadata", {})
    tenant_id = metadata.get("tenant_id")
    plan = metadata.get("plan")

    if not tenant_id or not plan:
        logger.error("[Billing] Missing metadata in checkout.session.completed")
        return

    if plan not in VALID_PLANS:
        logger.error(f"[Billing] Invalid plan in webhook metadata: {plan}")
        return

    result = await db.execute(select(User).where(User.id == tenant_id))
    user = result.scalar_one_or_none()

    if user:
        user.plan = plan
        user.stripe_customer_id = session.get("customer")
        user.stripe_subscription_id = session.get("subscription")
        await db.flush()
        logger.info(f"[Billing] Updated tenant {tenant_id} → plan={plan}")
    else:
        logger.error(f"[Billing] User not found for tenant_id={tenant_id}")


async def _handle_subscription_cancelled(subscription: dict, db: AsyncSession) -> None:
    """Downgrade user to free plan on subscription cancellation."""
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
    user = result.scalar_one_or_none()

    if user:
        user.plan = "free"
        await db.flush()
        logger.info(f"[Billing] Downgraded customer {customer_id} → free plan")
