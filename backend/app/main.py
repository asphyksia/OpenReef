from contextlib import asynccontextmanager
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import auth, datasets, health, jobs, models, payments, providers
from app.config import settings
from app.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate production secrets on startup
    settings.validate_production()

    # Warn if running with weak secrets in non-mock mode
    if settings.ogpu_adapter in ("local", "real"):
        if settings.jwt_secret == "dev-secret-change-me":
            warnings.warn(
                "SECURITY: Using default JWT_SECRET in non-mock mode. "
                "Set JWT_SECRET to a strong random value.",
                UserWarning,
            )
        if settings.r2_access_key_id == "minioadmin":
            warnings.warn(
                "SECURITY: Using default MinIO credentials in non-mock mode. "
                "Set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY to strong values.",
                UserWarning,
            )
    yield


app = FastAPI(title="OpenReef API", version="0.1.0", lifespan=lifespan)

# Use shared rate limiter instance
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Parse allowed origins from config (comma-separated)
_cors_origins = [o.strip() for o in settings.frontend_url.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Provider-Secret"],
    expose_headers=["X-CSRF-Token"],
)

# Routes
app.include_router(auth.router)
app.include_router(datasets.router)
app.include_router(jobs.router)
app.include_router(models.router)
app.include_router(payments.router)
app.include_router(providers.router)
app.include_router(health.router)
