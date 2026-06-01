"""Celery maintenance tasks: provider sync and stale job cleanup.

These tasks run periodically to keep the system healthy:
- sync_providers: Syncs provider hardware info from OGPU on-chain + IPFS
- check_stale_jobs: Fails jobs that have exceeded their heartbeat timeout
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def sync_providers(self):
    """Sync all providers registered to our source from on-chain + IPFS.

    This task should be run periodically (e.g. every 10 minutes) via Celery Beat
    or manually triggered by an admin.

    Uses asyncio.run() to execute the async SmartRoute.sync_all_providers()
    within a fresh event loop, with a proper async session.
    """
    from app.config import settings

    if settings.ogpu_adapter != "real":
        logger.info("Provider sync skipped — not in real mode")
        return {"synced": 0, "mode": settings.ogpu_adapter}

    source_address = settings.ogpu_source_address
    if not source_address:
        logger.warning("Provider sync skipped — OGPU_SOURCE_ADDRESS not configured")
        return {"synced": 0, "error": "No source address configured"}

    async def _do_sync():
        from app.database import async_session
        from app.services.smart_route import SmartRoute
        from sqlalchemy import select, func
        from app.models.provider import Provider

        async with async_session() as db:
            smart = SmartRoute(db)
            await smart.sync_all_providers(source_address)
            await db.commit()
            count = await db.scalar(select(func.count()).where(Provider.is_active == True))
            return count or 0

    try:
        count = asyncio.run(_do_sync())
        logger.info("Provider sync complete: %d active providers", count)
        return {"synced": count}
    except Exception as e:
        logger.error("Provider sync failed: %s", e)
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, max_retries=1)
def check_stale_jobs_task(self):
    """Find and fail jobs that have exceeded their heartbeat timeout.

    This task should be run periodically (e.g. every 5 minutes) via Celery Beat.
    """
    from app.tasks.stale_cleanup import check_stale_jobs

    try:
        processed = check_stale_jobs()
        return {"processed": processed}
    except Exception as e:
        logger.error("Stale job check failed: %s", e)
        raise self.retry(exc=e, countdown=300)
