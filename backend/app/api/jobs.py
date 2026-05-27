import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobEstimateResponse, JobResponse
from app.services import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    return [_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    download_url = None
    if job.output_r2_key:
        from app.services import storage_service
        download_url = storage_service.presigned_url(job.output_r2_key)
    return _to_response(job, download_url=download_url)


@router.get("/{job_id}/download", response_model=JobResponse)
async def download_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not job.output_r2_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No artifact available for this job")
    from app.services import storage_service
    download_url = storage_service.presigned_url(job.output_r2_key)
    return _to_response(job, download_url=download_url)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await job_service.create_job(
        db=db,
        user_id=user.id,
        dataset_id=body.dataset_id,
        base_model_id=body.base_model_id,
        preset=body.preset,
        adapter=body.adapter,
    )
    return _to_response(job)


@router.post("/{job_id}/confirm", response_model=JobResponse)
async def confirm_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await job_service.confirm_job(db, user.id, job_id)

    # Start the Celery task that publishes to OGPU and polls for completion
    from app.tasks.training import run_job
    run_job.delay(str(job.id))

    return _to_response(job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Use for_update to prevent race conditions on cancel
    result = await db.execute(
        select(Job).where(Job.id == job_id).with_for_update()
    )
    job = result.scalar_one_or_none()
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    cancellable = ("pending", "queued", "provisioning")
    if job.status not in cancellable:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot cancel job in status '{job.status}'")

    # Refund policy based on cancellation stage
    refund_pct = {
        "pending": 1.0,        # Not confirmed yet — full refund
        "queued": 0.5,         # Published to OGPU, no provider yet — 50% refund
        "provisioning": 0.0,   # Provider working — no refund
    }
    pct = refund_pct.get(job.status, 0)

    if job.estimated_cost and float(job.estimated_cost) > 0 and pct > 0:
        from app.services import credit_service
        refund_amount = float(job.estimated_cost) * pct
        await credit_service.refund_credits(
            db, user.id, refund_amount, job.id,
            f"Job cancelled ({int(pct * 100)}% refund — status: {job.status})"
        )

    # Cancel on-chain if task was published
    if job.ogpu_task_address and job.status in ("queued",):
        try:
            from app.services import ogpu_service
            ogpu_service.cancel_task_onchain(job.ogpu_task_address)
        except Exception:
            pass  # Best effort; chain may have already finalized

    job.status = "cancelled"
    await db.commit()
    await db.refresh(job)
    return _to_response(job)


def _to_response(j: Job, *, download_url: str | None = None) -> JobResponse:
    return JobResponse(
        id=j.id,
        dataset_id=j.dataset_id,
        base_model_id=j.base_model_id,
        preset=j.preset,
        adapter=j.adapter,
        status=j.status,
        status_detail=j.status_detail,
        estimated_cost=float(j.estimated_cost) if j.estimated_cost else None,
        actual_cost=float(j.actual_cost) if j.actual_cost else None,
        progress_pct=j.progress_pct,
        error_message=j.error_message,
        ogpu_task_address=j.ogpu_task_address,
        requeue_count=j.requeue_count,
        provider_address=j.provider_address,
        download_url=download_url,
        created_at=j.created_at.isoformat() if j.created_at else "",
        started_at=j.started_at.isoformat() if j.started_at else None,
        completed_at=j.completed_at.isoformat() if j.completed_at else None,
    )
