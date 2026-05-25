import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_model import BaseModel as DBBaseModel
from app.models.dataset import Dataset
from app.models.job import Job
from app.services import credit_service

# Pricing: rough USD estimate per job based on model size and preset
# In production this would query OGPU for real-time pricing.
PRICING = {
    # (param_count) -> base hourly rate * estimated hours by preset
    "fast": {"hours": 1, "multiplier": 1.0},
    "balanced": {"hours": 2, "multiplier": 1.0},
    "quality": {"hours": 4, "multiplier": 1.0},
}

HOURLY_RATE_7B = 0.50   # USD/hr estimate for 7B on OGPU
HOURLY_RATE_13B = 1.00  # USD/hr estimate for 13B on OGPU
BUFFER = 1.05            # 5% buffer


async def estimate_cost(db: AsyncSession, base_model_id: uuid.UUID, preset: str) -> float:
    model = await db.get(DBBaseModel, base_model_id)
    if model is None or not model.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base model")

    if preset not in PRICING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid preset")

    pricing = PRICING[preset]
    hourly_rate = HOURLY_RATE_13B if model.param_count >= 13 else HOURLY_RATE_7B
    base_cost = hourly_rate * pricing["hours"] * pricing["multiplier"]
    return round(base_cost * BUFFER, 2)


async def has_active_job(db: AsyncSession, user_id: uuid.UUID) -> bool:
    active_statuses = ("pending", "queued", "provisioning", "running")
    result = await db.execute(
        select(Job.id).where(Job.user_id == user_id, Job.status.in_(active_statuses)).limit(1)
    )
    return result.first() is not None


async def create_job(
    db: AsyncSession, user_id: uuid.UUID, dataset_id: uuid.UUID, base_model_id: uuid.UUID, preset: str, adapter: str
) -> Job:
    if adapter not in ("lora", "qlora"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid adapter")

    if await has_active_job(db, user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already have an active job")

    model = await db.get(DBBaseModel, base_model_id)
    if model is None or not model.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base model")

    estimated_cost = await estimate_cost(db, base_model_id, preset)

    balance = await credit_service.get_balance(db, user_id)
    if balance < estimated_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Need ${estimated_cost}, have ${balance}",
        )

    # Verify dataset belongs to user
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    job = Job(
        user_id=user_id,
        dataset_id=dataset_id,
        base_model_id=base_model_id,
        preset=preset,
        adapter=adapter,
        status="pending",
        estimated_cost=estimated_cost,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def confirm_job(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    # Use for_update to prevent race conditions on double-confirm
    result = await db.execute(
        select(Job).where(Job.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if job.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job cannot be confirmed in status '{job.status}'")

    # Charge the estimated cost
    await credit_service.charge_credits(
        db, user_id, float(job.estimated_cost), job.id, f"Fine-tuning job {job.id}"
    )

    job.status = "queued"
    await db.commit()
    await db.refresh(job)
    return job
