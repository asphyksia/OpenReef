"""Provider API endpoints for heartbeat, cancel, and stats."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_sync_engine
from app.limiter import limiter
from app.models.job import Job
from app.services import credit_service, provider_service
from app.services.pricing import MAX_REQUEUE

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _validate_provider_secret(x_provider_secret: str | None = Header(None)):
    """Validate provider API secret from header. Must be present AND match."""
    if x_provider_secret is None or x_provider_secret != settings.provider_api_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid provider secret")


@router.post("/{address}/heartbeat/{job_id}")
@limiter.limit("30/minute")
def heartbeat(
    request: Request,
    address: str,
    job_id: uuid.UUID,
    _: None = Depends(_validate_provider_secret),
):
    engine = get_sync_engine()
    with Session(engine) as db:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if job.status not in ("running", "checkpointing"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job not in running status")

        provider_service.record_heartbeat(db, address, job_id)
        db.commit()

        return {"ok": True, "job_id": str(job_id)}


@router.post("/{address}/cancel-job/{job_id}")
@limiter.limit("10/minute")
def cancel_job(
    request: Request,
    address: str,
    job_id: uuid.UUID,
    _: None = Depends(_validate_provider_secret),
):
    engine = get_sync_engine()
    with Session(engine) as db:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        if job.status not in ("running", "checkpointing"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job not in running status")

        # Ensure provider exists for tracking
        provider_service.ensure_provider(db, address)

        if job.requeue_count >= MAX_REQUEUE:
            # Max requeues reached — mark failed, full refund
            job.status = "failed"
            job.error_message = f"Provider {address} abandoned job after {MAX_REQUEUE} requeues"
            provider_service.record_provider_failure(db, address)
            # Full refund
            credit_service.refund_credits_sync(db, job.user_id, float(job.estimated_cost), job.id, description="Refund: provider abandoned job")
            db.commit()
            return {"status": "failed", "requeue_count": job.requeue_count, "refund": True}
        else:
            # Requeue the job
            provider_service.record_provider_cancel(db, job)
            db.commit()
            # Re-enqueue Celery task to resume polling
            from app.tasks.training import run_job
            run_job.apply_async(args=[str(job_id)], countdown=5)
            return {"status": "queued", "requeue_count": job.requeue_count, "refund": False}


@router.get("/{address}")
@limiter.limit("30/minute")
def get_provider_stats(
    request: Request,
    address: str,
    _: None = Depends(_validate_provider_secret),
):
    engine = get_sync_engine()
    with Session(engine) as db:
        stats = provider_service.get_provider_stats(db, address)
        if stats is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
        return stats
