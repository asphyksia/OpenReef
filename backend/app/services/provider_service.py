import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.provider import Provider

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_provider(session: Session, address: str) -> Provider:
    """Upsert provider record, ensuring it exists with last_active set."""
    provider = session.get(Provider, address)
    if provider is None:
        provider = Provider(address=address, last_active=_utc_now())
        session.add(provider)
        session.flush()
    else:
        provider.last_active = _utc_now()
    return provider


def record_heartbeat(session: Session, address: str, job_id) -> None:
    """Update job last_heartbeat and ensure provider record exists."""
    provider = ensure_provider(session, address)
    job = session.get(Job, job_id)
    if job is not None:
        job.last_heartbeat = _utc_now()
        if job.provider_address is None:
            job.provider_address = address


def record_provider_cancel(session: Session, job: Job) -> None:
    """Increment requeue_count and track abandonment on provider."""
    job.requeue_count += 1
    job.status = "queued"

    if job.provider_address:
        provider = ensure_provider(session, job.provider_address)
        provider.abandoned_count += 1
        provider.last_abandoned_at = _utc_now()


def record_provider_completion(session: Session, address: str) -> None:
    """Increment completed_count for provider."""
    if not address:
        return
    provider = ensure_provider(session, address)
    provider.completed_count += 1


def record_provider_failure(session: Session, address: str) -> None:
    """Increment failed_count for provider."""
    if not address:
        return
    provider = ensure_provider(session, address)
    provider.failed_count += 1


def get_provider_stats(session: Session, address: str) -> dict | None:
    """Return provider reputation stats or None if provider not found."""
    provider = session.get(Provider, address)
    if provider is None:
        return None
    return {
        "address": provider.address,
        "completed": provider.completed_count,
        "failed": provider.failed_count,
        "abandoned": provider.abandoned_count,
        "last_active": provider.last_active.isoformat() if provider.last_active else None,
        "last_abandoned_at": provider.last_abandoned_at.isoformat() if provider.last_abandoned_at else None,
    }


def evaluate_provider_penalty(session: Session, address: str) -> bool:
    """Evaluate if a provider should be blocked based on reputation.
    
    Blocks if fail_rate > 50% with minimum 5 total jobs.
    Returns True if provider was blocked, False otherwise.
    """
    provider = session.get(Provider, address)
    if provider is None or provider.is_blocked:
        return False

    total = provider.completed_count + provider.failed_count + provider.abandoned_count
    if total < 5:
        return False  # Not enough data

    fail_rate = (provider.failed_count + provider.abandoned_count) / total
    if fail_rate > 0.5:
        provider.is_blocked = True
        provider.blocked_at = _utc_now()
        provider.blocked_reason = f"High fail rate: {fail_rate:.0%} ({provider.failed_count} failed, {provider.abandoned_count} abandoned out of {total} total)"
        logger.warning("Provider %s blocked: %s", address, provider.blocked_reason)
        return True
    return False


def unblock_provider(session: Session, address: str) -> bool:
    """Manually unblock a provider. Returns True if unblocked."""
    provider = session.get(Provider, address)
    if provider is None:
        return False
    if not provider.is_blocked:
        return False
    provider.is_blocked = False
    provider.blocked_at = None
    provider.blocked_reason = None
    logger.info("Provider %s unblocked manually", address)
    return True


def mark_provider_inactive(session: Session, address: str) -> None:
    """Mark a provider as inactive (no recent heartbeat)."""
    provider = session.get(Provider, address)
    if provider:
        provider.is_active = False
