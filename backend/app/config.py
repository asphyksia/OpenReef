import os
import warnings
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5444/openreef"
    redis_url: str = "redis://127.0.0.1:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 4320

    r2_endpoint_url: str = "http://127.0.0.1:9000"
    r2_access_key_id: str = "minioadmin"
    r2_secret_access_key: str = "minioadmin"
    r2_bucket_name: str = "openreef-mvp"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""

    # OGPU adapter: mock (local dev), real (production), or local (local machine)
    ogpu_adapter: str = "mock"
    provider_api_secret: str = os.environ.get("PROVIDER_API_SECRET", "dev-secret-change-me")

    # OGPU Network (only needed when ogpu_adapter=real)
    client_private_key: str = ""
    ogpu_source_address: str = ""
    ogpu_use_testnet: str = "true"

    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    # Email (Resend)
    resend_api_key: str = ""
    email_from: str = "OpenReef <onboarding@resend.dev>"
    email_verification_enabled: bool = False

    @property
    def app_url(self) -> str:
        """Single base URL for the app (first entry in frontend_url list)."""
        return self.frontend_url.split(",")[0].strip()

    # Cookie settings
    cookie_secure: bool = False  # True in production (requires HTTPS)
    cookie_max_age: int = 7 * 24 * 3600  # 7 days

    # AMD ROCm overrides (loaded from .env.local, not committed)
    hsa_override_gfx_version: str | None = None
    torch_rocm_aotriton_enable_experimental: str | None = None

    model_config = {"env_file": (".env", ".env.local"), "extra": "ignore"}

    @field_validator("ogpu_adapter")
    @classmethod
    def validate_adapter(cls, v):
        if v not in ("mock", "real", "local"):
            raise ValueError("ogpu_adapter must be mock, real, or local")
        return v

    def validate_production(self) -> None:
        """Fail startup if required secrets are missing in production mode."""
        if self.ogpu_adapter == "real":
            missing = []
            if self.jwt_secret == "dev-secret-change-me":
                missing.append("JWT_SECRET")
            if self.provider_api_secret == "dev-secret-change-me":
                missing.append("PROVIDER_API_SECRET")
            if not self.stripe_secret_key or "placeholder" in self.stripe_secret_key:
                missing.append("STRIPE_SECRET_KEY (must be a real key, not empty or placeholder)")
            if not self.stripe_webhook_secret:
                missing.append("STRIPE_WEBHOOK_SECRET")
            if not self.stripe_publishable_key:
                missing.append("STRIPE_PUBLISHABLE_KEY")
            if self.client_private_key == "":
                missing.append("CLIENT_PRIVATE_KEY")
            if not self.cookie_secure:
                missing.append("COOKIE_SECURE (must be true in production)")
            if self.frontend_url.startswith("http://"):
                missing.append("FRONTEND_URL (must be HTTPS in production)")
            if self.api_url.startswith("http://"):
                missing.append("API_URL (must be HTTPS in production)")
            if self.email_verification_enabled and not self.resend_api_key:
                missing.append("RESEND_API_KEY (required when EMAIL_VERIFICATION_ENABLED=true)")
            if missing:
                raise RuntimeError(
                    f"Missing required settings for production: {', '.join(missing)}"
                )


settings = Settings()

# Propagate ROCm overrides to os.environ for subprocesses
if settings.hsa_override_gfx_version:
    os.environ["HSA_OVERRIDE_GFX_VERSION"] = settings.hsa_override_gfx_version
if settings.torch_rocm_aotriton_enable_experimental:
    os.environ["TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL"] = settings.torch_rocm_aotriton_enable_experimental

# Warn if running with default JWT secret in non-mock mode
if settings.jwt_secret == "dev-secret-change-me" and settings.ogpu_adapter == "mock":
    warnings.warn("Using default JWT_SECRET — fine for development only", UserWarning)
