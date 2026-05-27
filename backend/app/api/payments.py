import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.credit_ledger import ProcessedEvent
from app.schemas.payment import BalanceResponse, CheckoutSessionRequest, DevAddCreditsRequest
from app.services import credit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    balance = await credit_service.get_balance(db, user.id)
    return BalanceResponse(balance=balance)


@router.post("/checkout-session")
async def create_checkout_session(
    body: CheckoutSessionRequest,
    user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout Session to add credits."""
    if settings.ogpu_adapter != "real":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stripe not configured (dev mode)")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"OpenReef Credits - ${body.amount_usd:.2f}",
                },
                "unit_amount": int(body.amount_usd * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{settings.frontend_url}/dashboard/credits?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/dashboard/credits",
        metadata={"user_id": str(user.id)},
    )
    return {"checkout_url": session.url}


@router.post("/dev-add-credits")
async def dev_add_credits(
    body: DevAddCreditsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Development-only: add credits without Stripe. Only available when OGPU_ADAPTER=mock."""
    if settings.ogpu_adapter != "mock":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev credits disabled in production")
    await credit_service.add_credits(db, user.id, body.amount, "Dev credits (MVP testing)")
    await db.commit()
    balance = await credit_service.get_balance(db, user.id)
    return {"balance": balance}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    import stripe
    stripe.api_key = settings.stripe_secret_key

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, TypeError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    # Idempotency: skip already-processed events
    existing = await db.execute(select(ProcessedEvent).where(ProcessedEvent.event_id == event["id"]))
    if existing.scalar_one_or_none():
        return {"received": True, "duplicate": True}

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id_str = session.get("metadata", {}).get("user_id")
        amount_total = session.get("amount_total", 0) / 100.0

        if user_id_str:
            await credit_service.add_credits(
                db, uuid.UUID(user_id_str), amount_total, f"Stripe payment {session['id']}"
            )
            db.add(ProcessedEvent(event_id=event["id"]))
            await db.commit()
            return {"received": True}

    # Mark non-payment events as processed too
    db.add(ProcessedEvent(event_id=event["id"]))
    await db.commit()
    return {"received": True}
