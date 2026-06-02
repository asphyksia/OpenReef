import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_model import BaseModel as DBBaseModel
from app.models.dataset import Dataset
from app.models.job import Job
from app.services import credit_service, pricing

HOURLY_RATE_7B = 0.50   # USD/hr estimate for 7B on OGPU
HOURLY_RATE_13B = 1.00  # USD/hr estimate for 13B on OGPU
BUFFER = 1.05            # 5% buffer


async def estimate_cost(db: AsyncSession, base_model_id: uuid.UUID, preset: str, token_count: int = 0) -> float:
    model = await db.get(DBBaseModel, base_model_id)
    if model is None or not model.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid base model")

    if preset not in pricing.PRESET_HOURS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid preset")

    est_hours = pricing.PRESET_HOURS[preset]
    hourly_rate = HOURLY_RATE_13B if model.param_count >= 13 else HOURLY_RATE_7B

    # Adjust cost based on dataset size (min 30% of base cost)
    if token_count > 0:
        token_factor = min(token_count / 100_000, 1.0)
        est_hours = est_hours * (0.3 + 0.7 * token_factor)

    return round(hourly_rate * est_hours * BUFFER, 2)


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

    # Verify dataset belongs to user and get token_count for cost estimation
    dataset = await db.get(Dataset, dataset_id)
    if dataset is None or dataset.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    token_count = dataset.token_count or 0
    estimated_cost = await estimate_cost(db, base_model_id, preset, token_count)

    balance = await credit_service.get_balance(db, user_id)
    if balance < estimated_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Need ${estimated_cost}, have ${balance}",
        )

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

    # Idempotency: if already confirmed (queued), return without charging again
    if job.status == "queued":
        return job

    if job.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Job cannot be confirmed in status '{job.status}'")

    # Lock user's credit ledger rows to prevent concurrent overdrafts
    balance = await credit_service.get_balance_for_update(db, user_id)
    estimated_cost = float(job.estimated_cost)
    if balance < estimated_cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient balance. Need ${estimated_cost:.2f}, have ${balance:.2f}",
        )

    # Charge the estimated cost (no commit — caller controls transaction)
    await credit_service.charge_credits(
        db, user_id, estimated_cost, job.id, f"Fine-tuning job {job.id}"
    )

    job.status = "queued"
    await db.commit()
    await db.refresh(job)
    return job
