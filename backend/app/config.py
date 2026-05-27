import os
import warnings
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

    # OGPU adapter: mock (local dev) or real (production)
    ogpu_adapter: str = "mock"
    provider_api_secret: str = os.environ.get("PROVIDER_API_SECRET", "dev-secret-change-me")

    # OGPU Network (only needed when ogpu_adapter=real)
    client_private_key: str = ""
    ogpu_source_address: str = ""
    ogpu_use_testnet: str = "true"

    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    # Cookie settings
    cookie_secure: bool = False  # True in production (requires HTTPS)
    cookie_max_age: int = 7 * 24 * 3600  # 7 days

    model_config = {"env_file": ".env"}

    def validate_production(self) -> None:
        """Fail startup if required secrets are missing in production mode."""
        if self.ogpu_adapter == "real":
            missing = []
            if self.jwt_secret == "dev-secret-change-me":
                missing.append("JWT_SECRET")
            if self.stripe_secret_key and "placeholder" in self.stripe_secret_key:
                missing.append("STRIPE_SECRET_KEY (must be a real key)")
            if self.client_private_key == "":
                missing.append("CLIENT_PRIVATE_KEY")
            if missing:
                raise RuntimeError(
                    f"Missing required secrets for production: {', '.join(missing)}"
                )


settings = Settings()

# Warn if running with default JWT secret in non-mock mode
if settings.jwt_secret == "dev-secret-change-me" and settings.ogpu_adapter == "mock":
    warnings.warn("Using default JWT_SECRET — fine for development only", UserWarning)
