"""Celery task for OGPU job lifecycle: publish + poll until terminal state."""

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.tasks.celery_app import celery_app

# Import all models so SQLAlchemy has the full schema
from app.models import user, dataset, job, credit_ledger, base_model, provider  # noqa: F401

# Sync engine for Celery tasks (avoids asyncpg event loop issues)
def _build_sync_url():
    """Convert asyncpg URL to psycopg2 URL."""
    url = settings.database_url
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

sync_engine = create_engine(_build_sync_url())

_MOCK = os.environ.get("OGPU_ADAPTER", "mock").lower() != "real"
POLL_INTERVAL = 5 if _MOCK else 30
MAX_RETRIES = 20 if _MOCK else 240
MAX_REQUEUE = 2  # Max times a job can be requeued (3 total attempts)


@celery_app.task(name="tasks.training.run_job")
def run_job(job_id: str):
    """Run a fine-tuning job: publish to OGPU, then poll until completion."""
    import uuid

    from app.models.job import Job
    from app.models.base_model import BaseModel as DBBaseModel
    from app.services import credit_service, ogpu_service, provider_service

    with Session(sync_engine) as session:
        job = session.get(Job, uuid.UUID(job_id))
        if job is None:
            return

        # Phase 1: First execution — publish the task
        if job.ogpu_task_address is None:
            try:
                base_model = session.get(DBBaseModel, job.base_model_id)
                if base_model is None:
                    raise ValueError(f"Base model {job.base_model_id} not found")

                dataset_url = f"r2://{job.dataset_id}"
                axolotl = ogpu_service.AxolotlConfig(
                    base_model=base_model.name,
                    dataset_url=dataset_url,
                    preset=job.preset,
                    adapter=job.adapter,
                    output_bucket=f"models/{job.user_id}/{job.id}",
                )
                config = ogpu_service.build_task_config(axolotl)

                source_address = ogpu_service.get_finetune_source_address()
                ogpu_payment = int(float(job.estimated_cost) * 1e17) if not _MOCK else 100

                task_address = ogpu_service.publish_finetune_task(
                    source_address=source_address,
                    config=config,
                    payment_ogpu_wei=ogpu_payment,
                )

                job.ogpu_task_address = task_address
                job.status = "queued"
                mode = "mock" if _MOCK else "real"
                job.status_detail = f"Task published ({mode}), waiting for providers..."
                session.commit()
            except Exception as e:
                job.status = "failed"
                job.error_message = f"Failed to publish OGPU task: {str(e)}"
                job.completed_at = datetime.utcnow()
                session.commit()
                # Retry once after 60s
                run_job.apply_async(args=[job_id], countdown=60)
                return

        # Phase 2: All executions (including retries) — poll status
        if not job.ogpu_task_address:
            job.status = "failed"
            job.error_message = "No OGPU task address found"
            job.completed_at = datetime.utcnow()
            session.commit()
            return

        try:
            status_info = ogpu_service.get_task_status(job.ogpu_task_address)
            chain_status = status_info["status_name"]

            status_map = {
                "new": "queued",
                "attempted": "running",
                "responded": "completed",
                "finalized": "completed",
                "expired": "failed",
                "canceled": "cancelled",
            }

            new_status = status_map.get(chain_status, job.status)
            attempter_count = status_info.get("attempter_count", 0)

            # Track provider address from first attempter when job starts running
            if new_status == "running" and job.status != "running":
                job.status = "running"
                job.status_detail = f"Provider running ({attempter_count} attempter(s))"
                job.started_at = datetime.utcnow()
                job.progress_pct = max(job.progress_pct, 10)
                if attempter_count > 0 and job.provider_address is None:
                    job.provider_address = status_info.get("attempter_address")

            elif new_status == "completed" and job.status != "completed":
                job.status = "completed"
                job.status_detail = "Training complete"
                job.progress_pct = 100
                job.completed_at = datetime.utcnow()

                result = ogpu_service.get_task_result(job.ogpu_task_address)
                if result and isinstance(result, dict):
                    job.output_r2_key = result.get(
                        "output_key", f"models/{job.user_id}/{job.id}/adapter/"
                    )

                # Track provider who completed the job — prefer winning_provider from SDK
                winner = status_info.get("winning_provider") or job.provider_address
                if winner:
                    provider_service.record_provider_completion(session, winner)
                    job.provider_address = winner

            elif chain_status == "expired" and job.status not in ("completed", "failed"):
                if job.requeue_count >= MAX_REQUEUE:
                    job.status = "failed"
                    job.error_message = f"OGPU task expired after {MAX_REQUEUE + 1} attempts"
                    job.completed_at = datetime.utcnow()
                    if job.provider_address:
                        provider_service.record_provider_failure(session, job.provider_address)
                    if job.estimated_cost and float(job.estimated_cost) > 0:
                        credit_service.refund_credits_sync(session, job.user_id, float(job.estimated_cost), job.id, description="OGPU task expired after max requeues")
                else:
                    job.requeue_count += 1
                    job.status = "queued"
                    job.started_at = None
                    job.status_detail = f"Provider expired, requeued (attempt {job.requeue_count + 1}/3)"
                    if job.provider_address:
                        provider_service.record_provider_failure(session, job.provider_address)
                    session.commit()
                    run_job.apply_async(args=[job_id], countdown=POLL_INTERVAL)
                    return

            elif chain_status == "canceled" and job.status not in ("completed", "failed", "cancelled"):
                job.status = "cancelled"
                job.completed_at = datetime.utcnow()
                if job.provider_address:
                    provider_service.record_provider_failure(session, job.provider_address)

            session.commit()

            # Only retry if not in terminal state
            if chain_status not in ("responded", "finalized", "expired", "canceled"):
                run_job.apply_async(args=[job_id], countdown=POLL_INTERVAL)
                return

        except Exception:
            run_job.apply_async(args=[job_id], countdown=POLL_INTERVAL)
            return
