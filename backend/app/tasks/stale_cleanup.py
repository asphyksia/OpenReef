"""Celery task for proactive stale job cleanup and provider penalty evaluation.

Runs periodically (e.g. every 5 minutes) to detect and fail jobs that have
exceeded their heartbeat timeout, and to evaluate provider penalties.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.job import Job
from app.models.provider import Provider
from app.services import credit_service, provider_service

logger = logging.getLogger(__name__)

# Jobs without heartbeat for more than this are considered stale
HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes


def _build_sync_url():
    """Convert asyncpg URL to psycopg2 URL."""
    url = settings.database_url
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def _get_sync_engine():
    """Lazy init to avoid crash at import time if DB is not ready."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(_build_sync_url())
    return _sync_engine


_sync_engine = None


def check_stale_jobs():
    """Find and fail jobs that have exceeded their heartbeat timeout.
    
    Called periodically by Celery Beat or cron.
    Returns count of jobs processed.
    """
    engine = _get_sync_engine()
    processed = 0

    with Session(engine) as session:
        # Find jobs in non-terminal states without recent heartbeat
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
        stale_jobs = session.execute(
            select(Job).where(
                Job.status.in_(["running", "queued", "provisioning", "checkpointing"]),
                Job.last_heartbeat != None,
                Job.last_heartbeat < cutoff,
            )
        ).scalars().all()

        for job in stale_jobs:
            logger.warning("Stale job detected: %s (last heartbeat: %s, status: %s)",
                          job.id, job.last_heartbeat, job.status)

            job.status = "failed"
            job.error_message = f"Job lost heartbeat after {HEARTBEAT_TIMEOUT_SECONDS}s — provider may have disconnected"
            job.completed_at = datetime.now(timezone.utc)

            # Refund credits
            if job.estimated_cost and float(job.estimated_cost) > 0:
                credit_service.refund_credits_sync(
                    session, job.user_id, float(job.estimated_cost), job.id,
                    description="Job lost heartbeat — provider disconnected"
                )

            # Mark provider inactive and evaluate penalty
            if job.provider_address:
                provider_service.mark_provider_inactive(session, job.provider_address)
                provider_service.evaluate_provider_penalty(session, job.provider_address)

            processed += 1

        session.commit()

    # Also evaluate penalty for all providers with recent failures
    with Session(engine) as session:
        providers = session.execute(select(Provider)).scalars().all()
        for provider in providers:
            try:
                provider_service.evaluate_provider_penalty(session, provider.address)
            except Exception as e:
                logger.warning("Error evaluating penalty for %s: %s", provider.address, e)
        session.commit()

    if processed > 0:
        logger.info("Stale job cleanup: %d jobs failed", processed)

    return processed
