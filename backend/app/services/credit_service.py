import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_ledger import CreditLedger

if TYPE_CHECKING:
    DbSession = AsyncSession
else:
    DbSession = Session


async def get_balance(db: DbSession, user_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount), 0))
        .where(CreditLedger.user_id == user_id)
    )
    return float(result.scalar())


async def get_balance_for_update(db: DbSession, user_id: uuid.UUID) -> float:
    """Lock user's ledger rows before reading balance to prevent concurrent modifications.
    PostgreSQL doesn't allow FOR UPDATE with aggregate functions, so we lock first then sum.
    """
    # Step 1: lock all ledger rows for this user
    await db.execute(
        select(CreditLedger.id)
        .where(CreditLedger.user_id == user_id)
        .with_for_update(skip_locked=True)
    )
    # Step 2: sum without for_update
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount), 0))
        .where(CreditLedger.user_id == user_id)
    )
    return float(result.scalar())


def _add_ledger_entry(db: Session, user_id: uuid.UUID, amount: float, type: str, job_id: uuid.UUID | None = None, description: str = "") -> None:
    """Sync helper to add a credit ledger entry."""
    entry = CreditLedger(user_id=user_id, amount=amount, type=type, job_id=job_id, description=description)
    db.add(entry)


async def add_credits(db: DbSession, user_id: uuid.UUID, amount: float, description: str = "Stripe purchase") -> None:
    _add_ledger_entry(db, user_id, amount, "purchase", description=description)


async def charge_credits(db: DbSession, user_id: uuid.UUID, amount: float, job_id: uuid.UUID, description: str = "Job charge") -> None:
    balance = await get_balance(db, user_id)
    if balance < amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Need ${amount:.2f}, have ${balance:.2f}",
        )
    _add_ledger_entry(db, user_id, -abs(amount), "job_charge", job_id=job_id, description=description)


def refund_credits_sync(db: Session, user_id: uuid.UUID, amount: float, job_id: uuid.UUID, description: str = "Job refund") -> None:
    """Sync version for provider API and Celery tasks."""
    _add_ledger_entry(db, user_id, abs(amount), "refund", job_id=job_id, description=description)


async def refund_credits(db: DbSession, user_id: uuid.UUID, amount: float, job_id: uuid.UUID, description: str = "Job refund") -> None:
    _add_ledger_entry(db, user_id, abs(amount), "refund", job_id=job_id, description=description)
