from datetime import datetime, timezone

_UTC_NOW = lambda: datetime.now(timezone.utc)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.provider import Provider


def ensure_provider(session: Session, address: str) -> Provider:
    """Upsert provider record, ensuring it exists with last_active set."""
    provider = session.get(Provider, address)
    if provider is None:
        provider = Provider(address=address, last_active=_UTC_NOW())
        session.add(provider)
        session.flush()
    else:
        provider.last_active = _UTC_NOW()
    return provider


def record_heartbeat(session: Session, address: str, job_id) -> None:
    """Update job last_heartbeat and ensure provider record exists."""
    provider = ensure_provider(session, address)
    job = session.get(Job, job_id)
    if job is not None:
        job.last_heartbeat = _UTC_NOW()
        if job.provider_address is None:
            job.provider_address = address


def record_provider_cancel(session: Session, job: Job) -> None:
    """Increment requeue_count and track abandonment on provider."""
    job.requeue_count += 1
    job.status = "queued"

    if job.provider_address:
        provider = ensure_provider(session, job.provider_address)
        provider.abandoned_count += 1
        provider.last_abandoned_at = _UTC_NOW()


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
