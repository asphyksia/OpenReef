import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_ledger import CreditLedger


async def get_balance(db: AsyncSession, user_id: uuid.UUID) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount), 0))
        .where(CreditLedger.user_id == user_id)
    )
    return float(result.scalar())


async def add_credits(db: AsyncSession, user_id: uuid.UUID, amount: float, description: str = "Stripe purchase") -> None:
    entry = CreditLedger(user_id=user_id, amount=amount, type="purchase", description=description)
    db.add(entry)
    await db.commit()


async def charge_credits(db: AsyncSession, user_id: uuid.UUID, amount: float, job_id: uuid.UUID, description: str = "Job charge") -> None:
    entry = CreditLedger(user_id=user_id, amount=-abs(amount), type="job_charge", job_id=job_id, description=description)
    db.add(entry)
    await db.commit()


async def refund_credits(db: AsyncSession, user_id: uuid.UUID, amount: float, job_id: uuid.UUID, description: str = "Job refund") -> None:
    entry = CreditLedger(user_id=user_id, amount=abs(amount), type="refund", job_id=job_id, description=description)
    db.add(entry)
    await db.commit()
