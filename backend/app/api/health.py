"""Enhanced health endpoint with infrastructure checks and metrics."""
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.database import engine, get_sync_engine
from app.models.job import Job
from app.models.user import User
from app.models.provider import Provider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _verify_admin_key(request: Request) -> None:
    """Verify admin API key from Authorization: Bearer <key> header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not settings.admin_api_key or not hmac.compare_digest(
        auth[7:], settings.admin_api_key
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")


async def _check_database() -> tuple[bool, str]:
    """Check async PostgreSQL connection."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False, str(e)[:100]


def _check_redis() -> tuple[bool, str]:
    """Check Redis connection."""
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        return True, "connected"
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        return False, str(e)[:100]


def _check_storage() -> tuple[bool, str]:
    """Check MinIO/R2 storage connection."""
    try:
        from app.services.storage_service import _get_client, _bucket
        client = _get_client()
        client.head_bucket(Bucket=_bucket)
        return True, "connected"
    except Exception as e:
        logger.error("Storage health check failed: %s", e)
        return False, str(e)[:100]


def _get_metrics() -> dict:
    """Get usage metrics from database."""
    try:
        sync_engine = get_sync_engine()
        with sync_engine.connect() as conn:
            active_jobs = conn.execute(
                select(func.count()).select_from(Job).where(
                    Job.status.in_(("pending", "queued", "provisioning", "running", "checkpointing"))
                )
            ).scalar()

            total_users = conn.execute(
                select(func.count()).select_from(User)
            ).scalar()

            active_providers = conn.execute(
                select(func.count()).select_from(Provider).where(
                    Provider.is_active == True  # noqa: E712
                )
            ).scalar()

            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            jobs_24h = conn.execute(
                select(func.count()).select_from(Job).where(
                    Job.created_at >= cutoff
                )
            ).scalar()

        return {
            "active_jobs": active_jobs or 0,
            "total_users": total_users or 0,
            "active_providers": active_providers or 0,
            "jobs_last_24h": jobs_24h or 0,
        }
    except Exception as e:
        logger.error("Metrics collection failed: %s", e)
        return {
            "active_jobs": -1,
            "total_users": -1,
            "active_providers": -1,
            "jobs_last_24h": -1,
            "error": str(e)[:100],
        }


@router.get("/health")
async def health():
    """Basic health check — no dependencies."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready():
    """Readiness probe — checks all infrastructure dependencies.

    Returns 200 only when all services are connected.
    Returns 503 if any dependency is unhealthy.
    """
    db_ok, db_msg = await _check_database()
    redis_ok, redis_msg = _check_redis()
    storage_ok, storage_msg = _check_storage()

    all_healthy = db_ok and redis_ok and storage_ok

    result = {
        "status": "healthy" if all_healthy else "degraded",
        "database": {"status": "connected" if db_ok else "error", "detail": db_msg},
        "redis": {"status": "connected" if redis_ok else "error", "detail": redis_msg},
        "storage": {"status": "connected" if storage_ok else "error", "detail": storage_msg},
        "adapter": settings.ogpu_adapter,
    }

    if all_healthy:
        return result

    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=result)


@router.get("/admin/metrics")
async def admin_metrics(_: None = Depends(_verify_admin_key)):
    """Usage metrics — protected by admin API key.

    Requires Authorization: Bearer <ADMIN_API_KEY> header.
    """
    metrics = _get_metrics()
    return {"status": "ok", "metrics": metrics}
