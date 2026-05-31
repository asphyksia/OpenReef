"""Celery task for OGPU job lifecycle: publish + poll until terminal state."""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.services.pricing import MAX_REQUEUE, PRESET_HOURS, TIMEOUT_MULTIPLIER
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Import all models so SQLAlchemy has the full schema
from app.models import user, dataset, job, credit_ledger, base_model, provider  # noqa: F401

# Sync engine for Celery tasks (avoids asyncpg event loop issues)
def _build_sync_url():
    """Convert asyncpg URL to psycopg2 URL."""
    url = settings.database_url
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

sync_engine = None

def _get_sync_engine():
    """Lazy init to avoid crash at import time if DB is not ready."""
    global sync_engine
    if sync_engine is None:
        sync_engine = create_engine(_build_sync_url())
    return sync_engine

_ADAPTER_MODE = settings.ogpu_adapter
_MOCK = _ADAPTER_MODE == "mock"
_LOCAL = _ADAPTER_MODE == "local"

POLL_INTERVAL = 5 if _MOCK else 15 if _LOCAL else 30
MAX_RETRIES = 20 if _MOCK else 120 if _LOCAL else 240
MAX_PUBLISH_RETRIES = 1  # Max retries if OGPU task publish fails


def _calculate_timeout(preset: str, param_count_b: int) -> int:
    """Calculate timeout in seconds based on preset and model size."""
    est_hours = PRESET_HOURS.get(preset, 2)
    if param_count_b >= 13:
        est_hours *= 2
    return int(est_hours * 3600 * TIMEOUT_MULTIPLIER)


@celery_app.task(name="tasks.training.run_job", bind=True, max_retries=MAX_RETRIES)
def run_job(self, job_id: str):
    """Run a fine-tuning job: publish to OGPU, then poll until completion."""
    import uuid

    from app.models.dataset import Dataset
    from app.models.job import Job
    from app.models.base_model import BaseModel as DBBaseModel
    from app.services import credit_service, ogpu_service, provider_service

    with Session(_get_sync_engine()) as session:
        job = session.get(Job, uuid.UUID(job_id))
        if job is None:
            return

        # Idempotency guard: if job is already terminal, skip without side effects
        if job.status in ("completed", "failed", "cancelled", "refunded"):
            logger.info("Job %s already in terminal status '%s', skipping", job_id, job.status)
            return

        # Phase 1: First execution — publish the task
        if job.ogpu_task_address is None:
            # Atomic guard: mark as "provisioning" to prevent double-publish
            try:
                from sqlalchemy import text
                from sqlalchemy.exc import OperationalError
                lock_result = session.execute(
                    text("SELECT id, status FROM jobs WHERE id = :jid FOR UPDATE NOWAIT"),
                    {"jid": str(job_id)},
                )
                lock_row = lock_result.first()
                if lock_row is None:
                    logger.warning("Job %s disappeared during lock attempt", job_id)
                    return
                locked_status = lock_row[1]
                if locked_status not in ("pending", "queued"):
                    logger.info("Job %s status changed to '%s' during publish, skipping", job_id, locked_status)
                    session.rollback()
                    return

                # Mark as provisioning atomically
                job.status = "provisioning"
                job.status_detail = "Publishing OGPU task..."
                session.commit()
            except OperationalError:
                # Another worker holds the lock — this task is redundant
                logger.info("Job %s locked by another worker, skipping", job_id)
                return

            try:
                base_model = session.get(DBBaseModel, job.base_model_id)
                if base_model is None:
                    raise ValueError(f"Base model {job.base_model_id} not found")

                dataset = session.get(Dataset, job.dataset_id)
                if dataset is None:
                    raise ValueError(f"Dataset {job.dataset_id} not found")
                dataset_url = ogpu_service.resolve_dataset_url(dataset.r2_key)

                axolotl = ogpu_service.AxolotlConfig(
                    base_model=base_model.name,
                    dataset_url=dataset_url,
                    preset=job.preset,
                    adapter=job.adapter,
                    output_bucket=f"models/{job.user_id}/{job.id}",
                )
                config = ogpu_service.build_task_config(axolotl)

                source_address = ogpu_service.get_finetune_source_address()
                ogpu_payment = int(float(job.estimated_cost) * 1e17) if not (_MOCK or _LOCAL) else 100

                task_address = ogpu_service.publish_finetune_task(
                    source_address=source_address,
                    config=config,
                    payment_ogpu_wei=ogpu_payment,
                )

                job.ogpu_task_address = task_address
                job.status = "queued"
                mode = "mock" if _MOCK else "local" if _LOCAL else "real"
                job.status_detail = f"Task published ({mode}), waiting for providers..."
                session.commit()
            except Exception as e:
                job.status = "failed"
                job.error_message = f"Failed to publish OGPU task: {str(e)}"
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
                if job.requeue_count < MAX_PUBLISH_RETRIES:
                    job.requeue_count += 1
                    job.status = "pending"
                    job.error_message = None
                    job.completed_at = None
                    session.commit()
                    run_job.apply_async(args=[job_id], countdown=60)
                return

        # Phase 2: All executions (including retries) — poll status
        if not job.ogpu_task_address:
            job.status = "failed"
            job.error_message = "No OGPU task address found"
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
            return

        try:
            status_info = ogpu_service.get_task_status(job.ogpu_task_address)
            chain_status = status_info["status_name"]

            status_map = {
                "new": "queued",
                "attempted": "running",
                "responded": "running",  # Provider responded but artifact not ready yet
                "finalized": "completed",
                "expired": "failed",
                "canceled": "cancelled",
                "checkpointing": "checkpointing",  # Provider saving checkpoint, still running
            }

            new_status = status_map.get(chain_status, job.status)
            attempter_count = status_info.get("attempter_count", 0)

            # Track provider address from first attempter when job starts running
            if new_status == "running" and job.status != "running":
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
                job.progress_pct = max(job.progress_pct, 10)

                # Calculate dynamic timeout based on preset and model size
                base_model = session.get(DBBaseModel, job.base_model_id)
                timeout_seconds = _calculate_timeout(job.preset, base_model.param_count if base_model else 0)
                job.status_detail = f"Provider running (timeout: {timeout_seconds // 3600}h estimated)"
                if attempter_count > 0 and job.provider_address is None:
                    job.provider_address = status_info.get("attempter_address")

            elif new_status == "completed" and job.status not in ("completed", "cancelled"):
                result = ogpu_service.get_task_result(job.ogpu_task_address)
                if result and isinstance(result, dict):
                    if "output_key" in result:
                        # Mock mode: provider wrote directly to R2
                        job.output_r2_key = result["output_key"]
                    else:
                        # Real mode: bridge IPFS → R2
                        output_r2_key = f"models/{job.user_id}/{job.id}/adapter.safetensors"
                        from app.services import ogpu_service as _ogpu
                        adapter = _ogpu.get_adapter()
                        if hasattr(adapter, "retrieve_and_store_artifact"):
                            job.output_r2_key = adapter.retrieve_and_store_artifact(
                                job.ogpu_task_address, output_r2_key
                            )

                    # If we still don't have an artifact, wait for next poll
                    if not job.output_r2_key:
                        job.status = "running"
                        job.status_detail = "Awaiting artifact..."
                        session.commit()
                        return

                    # Validate the artifact before marking as completed
                    is_valid, reason = ogpu_service.validate_artifact(job.output_r2_key)
                    if not is_valid:
                        job.status = "failed"
                        job.error_message = f"Invalid output artifact: {reason}"
                        job.completed_at = datetime.now(timezone.utc)
                        winner = status_info.get("winning_provider") or job.provider_address
                        if winner:
                            provider_service.record_provider_failure(session, winner)
                            provider_service.evaluate_provider_penalty(session, winner)
                        if job.estimated_cost and float(job.estimated_cost) > 0:
                            credit_service.refund_credits_sync(session, job.user_id, float(job.estimated_cost), job.id, description="Invalid output artifact")
                        session.commit()
                        return

                    job.status = "completed"
                    job.status_detail = "Training complete"
                    job.progress_pct = 100
                    job.completed_at = datetime.now(timezone.utc)

                    # Track provider who completed the job — prefer winning_provider from SDK
                    winner = status_info.get("winning_provider") or job.provider_address
                    if winner:
                        provider_service.record_provider_completion(session, winner)
                        job.provider_address = winner

                    # Evaluate penalty for failed providers after a successful completion
                    # (check if any other providers should be blocked)
                    if job.provider_address:
                        provider_service.evaluate_provider_penalty(session, job.provider_address)
                else:
                    # finalized but no result data — fail with refund
                    job.status = "failed"
                    job.error_message = "Task finalized but no result data available"
                    job.completed_at = datetime.now(timezone.utc)
                    winner = status_info.get("winning_provider") or job.provider_address
                    if winner:
                        provider_service.record_provider_failure(session, winner)
                        provider_service.evaluate_provider_penalty(session, winner)
                    if job.estimated_cost and float(job.estimated_cost) > 0:
                        credit_service.refund_credits_sync(session, job.user_id, float(job.estimated_cost), job.id, description="No result data on finalized task")
                    session.commit()
                    return

            # Dynamic timeout check: fail job if running too long
            if job.status == "running" and job.started_at:
                elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
                base_model = session.get(DBBaseModel, job.base_model_id)
                timeout_seconds = _calculate_timeout(job.preset, base_model.param_count if base_model else 0)

                if elapsed > timeout_seconds:
                    job.status = "failed"
                    job.error_message = f"Job timed out ({elapsed / 3600:.1f}h > {timeout_seconds / 3600:.1f}h limit)"
                    job.completed_at = datetime.now(timezone.utc)
                    if job.provider_address:
                        provider_service.record_provider_failure(session, job.provider_address)
                        provider_service.evaluate_provider_penalty(session, job.provider_address)
                    if job.estimated_cost and float(job.estimated_cost) > 0:
                        credit_service.refund_credits_sync(session, job.user_id, float(job.estimated_cost), job.id, description="Job timed out")
                    session.commit()
                    return

            elif chain_status == "expired" and job.status not in ("completed", "failed"):
                if job.requeue_count >= MAX_REQUEUE:
                    job.status = "failed"
                    job.error_message = f"OGPU task expired after {MAX_REQUEUE + 1} attempts"
                    job.completed_at = datetime.now(timezone.utc)
                    if job.provider_address:
                        provider_service.record_provider_failure(session, job.provider_address)
                        provider_service.evaluate_provider_penalty(session, job.provider_address)
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
                job.completed_at = datetime.now(timezone.utc)
                if job.provider_address:
                    provider_service.record_provider_failure(session, job.provider_address)
                    provider_service.evaluate_provider_penalty(session, job.provider_address)

            session.commit()

            # Only retry if not in terminal state
            if chain_status not in ("finalized", "expired", "canceled"):
                run_job.apply_async(args=[job_id], countdown=POLL_INTERVAL)
                return

        except Exception as e:
            logger.exception("Poll error for job %s (attempt %d/%d)", job_id, self.request.retries + 1, MAX_RETRIES)
            if self.request.retries >= MAX_RETRIES - 1:
                # Max retries reached — mark job as failed
                with Session(_get_sync_engine()) as fail_session:
                    import uuid
                    from app.models.job import Job
                    failed_job = fail_session.get(Job, uuid.UUID(job_id))
                    if failed_job and failed_job.status not in ("completed", "failed", "cancelled"):
                        failed_job.status = "failed"
                        failed_job.error_message = f"Polling failed after {MAX_RETRIES} retries: {e}"
                        failed_job.completed_at = datetime.now(timezone.utc)
                        fail_session.commit()
                return
            raise self.retry(countdown=POLL_INTERVAL, exc=e)
