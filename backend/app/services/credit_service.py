import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_ledger import CreditLedger


async def get_balance(db: AsyncSession, user_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount), 0))
        .where(CreditLedger.user_id == user_id)
    )
    return float(result.scalar())


async def get_balance_for_update(db: AsyncSession, user_id: uuid.UUID) -> float:
    """Lock user's ledger rows before reading balance to prevent concurrent modifications."""
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount), 0))
        .where(CreditLedger.user_id == user_id)
        .with_for_update()
    )
    return float(result.scalar())


async def add_credits(db: AsyncSession, user_id: uuid.UUID, amount: float, description: str = "Stripe purchase") -> None:
    entry = CreditLedger(user_id=user_id, amount=amount, type="purchase", description=description)
    db.add(entry)


async def charge_credits(db: AsyncSession, user_id: uuid.UUID, amount: float, job_id: uuid.UUID, description: str = "Job charge") -> None:
    balance = await get_balance(db, user_id)
    if balance < amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Need ${amount:.2f}, have ${balance:.2f}",
        )
    entry = CreditLedger(user_id=user_id, amount=-abs(amount), type="job_charge", job_id=job_id, description=description)
    db.add(entry)


async def refund_credits(db: AsyncSession, user_id: uuid.UUID, amount: float, job_id: uuid.UUID, description: str = "Job refund") -> None:
    entry = CreditLedger(user_id=user_id, amount=abs(amount), type="refund", job_id=job_id, description=description)
    db.add(entry)
