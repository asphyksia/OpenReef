import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreateRequest, JobResponse
from app.services import job_service
from app.services.pricing import PRESET_HOURS, TIMEOUT_MULTIPLIER

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _estimate_timeout_seconds(preset: str, token_count: int = 0) -> int:
    """Conservative estimate of total job duration in seconds.

    Adjusts the base timeout based on dataset token count.
    A small dataset (few tokens) gets a shorter timeout.
    Normalized to 100k tokens as the reference point.
    """
    est_hours = PRESET_HOURS.get(preset, 2)
    base_timeout = int(est_hours * 3600 * TIMEOUT_MULTIPLIER)

    # Adjust timeout based on dataset size (min 30% of base timeout)
    if token_count > 0:
        token_factor = min(token_count / 100_000, 1.0)
        timeout = int(base_timeout * (0.3 + 0.7 * token_factor))
    else:
        timeout = base_timeout

    return timeout


async def _check_stale_job(job: Job, db: AsyncSession) -> Job:
    """Detect and fail jobs that have exceeded their timeout (zombie detection).

    If a job is in a non-terminal state but has been running longer than
    its estimated timeout, mark it as failed and refund credits.
    """
    if job.status not in ("queued", "provisioning", "running", "checkpointing"):
        return job
    if not job.started_at:
        return job

    # Get dataset token_count for timeout adjustment
    from app.models.dataset import Dataset
    dataset = await db.get(Dataset, job.dataset_id)
    token_count = dataset.token_count if dataset else 0

    timeout_seconds = _estimate_timeout_seconds(job.preset, token_count)
    now = datetime.now(timezone.utc)
    started = job.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    started = started.astimezone(timezone.utc)

    elapsed = (now - started).total_seconds()
    if elapsed <= timeout_seconds:
        return job

    # Job has exceeded timeout — mark as failed
    job.status = "failed"
    job.error_message = f"Job timed out ({elapsed / 3600:.1f}h > {timeout_seconds / 3600:.1f}h limit). Worker may have disconnected."
    job.completed_at = now
    job.progress_pct = min(int((elapsed / timeout_seconds) * 90 + 10), 99)

    # Refund credits
    if job.estimated_cost and float(job.estimated_cost) > 0:
        from app.services import credit_service
        await credit_service.refund_credits(
            db, job.user_id, float(job.estimated_cost), job.id,
            description="Job timed out — worker disconnected"
        )

    # Mark provider as inactive
    if job.provider_address:
        from app.services.smart_route import SmartRoute
        smart = SmartRoute(db)
        await smart.mark_provider_inactive(job.provider_address)

    await db.commit()
    await db.refresh(job)
    return job


def _compute_progress(job: Job, token_count: int = 0) -> tuple[int, str | None]:
    """Calculate dynamic progress percentage and ETA for running jobs.

    Returns (progress_pct, estimated_completion_iso).
    """
    progress_pct = job.progress_pct
    estimated_completion = None

    if job.status == "running" and job.started_at:
        timeout_seconds = _estimate_timeout_seconds(job.preset, token_count)
        now = datetime.now(timezone.utc)
        started = job.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        started = started.astimezone(timezone.utc)

        elapsed = (now - started).total_seconds()
        if elapsed > 0 and timeout_seconds > 0:
            progress_pct = min(int((elapsed / timeout_seconds) * 90 + 10), 99)
            eta = started + timedelta(seconds=timeout_seconds)
            estimated_completion = eta.isoformat()

    return progress_pct, estimated_completion


@router.get("", response_model=list[JobResponse])
async def list_jobs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models.dataset import Dataset

    result = await db.execute(
        select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    responses = []
    for j in jobs:
        j = await _check_stale_job(j, db)
        # Get dataset token_count for progress/timeout calculation
        dataset = await db.get(Dataset, j.dataset_id)
        token_count = dataset.token_count if dataset else 0
        progress_pct, estimated_completion = _compute_progress(j, token_count)
        responses.append(_to_response(j, progress_pct=progress_pct, estimated_completion=estimated_completion))
    return responses


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.dataset import Dataset

    job = await db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Lazy stale-job detection: fail jobs that exceeded timeout
    job = await _check_stale_job(job, db)

    # Get dataset token_count for progress/timeout calculation
    dataset = await db.get(Dataset, job.dataset_id)
    token_count = dataset.token_count if dataset else 0

    download_url = None
    if job.output_r2_key:
        from app.services import storage_service
        download_url = storage_service.presigned_url(job.output_r2_key)

    progress_pct, estimated_completion = _compute_progress(job, token_count)

    return _to_response(job, download_url=download_url,
                        progress_pct=progress_pct,
                        estimated_completion=estimated_completion)


@router.get("/{job_id}/download")
async def download_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Redirect to a presigned URL for downloading the job artifact.

    Returns a 302 redirect rather than the full JobResponse,
    since the download URL is the only useful information here.
    """
    from fastapi.responses import RedirectResponse

    job = await db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not job.output_r2_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No artifact available for this job")
    from app.services import storage_service
    download_url = storage_service.presigned_url(job.output_r2_key)
    return RedirectResponse(url=download_url)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
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
    # Pre-flight capacity check (real mode only)
    if settings.ogpu_adapter == "real":
        from app.services.smart_route import SmartRoute
        from app.services import ogpu_service
        from app.models.base_model import BaseModel as DBBaseModel

        job_peek = await db.get(Job, job_id)
        if job_peek and job_peek.user_id == user.id and job_peek.status == "pending":
            base_model = await db.get(DBBaseModel, job_peek.base_model_id)
            if base_model:
                source_address = settings.ogpu_source_address
                if not source_address:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="OGPU_SOURCE_ADDRESS not configured — cannot check provider capacity",
                    )
                smart = SmartRoute(db)
                # QLoRA is only routed to NVIDIA providers (bitsandbytes ROCm support is fragile)
                if not await smart.check_capacity(source_address, base_model.min_vram_gb, job_peek.adapter):
                    if job_peek.adapter == "qlora":
                        detail = f"No NVIDIA providers available for QLoRA on {base_model.name}. QLoRA requires NVIDIA GPUs. Try LoRA instead."
                    else:
                        detail = f"No providers available for {base_model.name} (requires {base_model.min_vram_gb}GB VRAM)"
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=detail,
                    )

    job = await job_service.confirm_job(db, user.id, job_id)

    # Only start the Celery task if this was a fresh confirm (status just changed to queued)
    # If the job was already queued (idempotent re-confirm), don't re-trigger
    if job.status == "queued" and job.ogpu_task_address is None:
        from app.tasks.training import run_job

        # Fire Celery task after a delay to ensure the commit is visible to workers.
        # The task itself has robust guards (FOR UPDATE NOWAIT, idempotency checks)
        # so even if it arrives early, it will skip gracefully rather than fail.
        # countdown=5 provides a safe margin for commit propagation.
        job_id_str = str(job.id)
        run_job.apply_async(args=[job_id_str], countdown=5)

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


def _to_response(j: Job, *, download_url: str | None = None, progress_pct: int | None = None, estimated_completion: str | None = None) -> JobResponse:
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
        progress_pct=progress_pct if progress_pct is not None else j.progress_pct,
        estimated_completion=estimated_completion,
        error_message=j.error_message,
        ogpu_task_address=j.ogpu_task_address,
        requeue_count=j.requeue_count,
        provider_address=j.provider_address,
        download_url=download_url,
        created_at=j.created_at.isoformat() if j.created_at else "",
        started_at=j.started_at.isoformat() if j.started_at else None,
        completed_at=j.completed_at.isoformat() if j.completed_at else None,
    )
