"""OGPU service — thin wrapper around the adapter for backward compatibility.

All callers should use this module. It delegates to either the mock or real adapter
based on the OGPU_ADAPTER env var.
"""

from app.services.ogpu_factory import get_adapter
from app.services.ogpu_adapter import AxolotlConfig, build_task_config, get_preset_params
from app.services.artifact_validation import validate_artifact

__all__ = [
    "get_adapter",
    "get_finetune_source_address",
    "publish_finetune_task",
    "get_task_status",
    "get_task_result",
    "cancel_task_onchain",
    "resolve_dataset_url",
    "AxolotlConfig",
    "build_task_config",
    "get_preset_params",
    "validate_artifact",
]


def get_finetune_source_address() -> str:
    return get_adapter().get_source_address()


def publish_finetune_task(
    source_address: str,
    config: dict,
    payment_ogpu_wei: int,
    expiry_minutes: int = 120,
) -> str:
    return get_adapter().publish_task(source_address, config, payment_ogpu_wei)


def get_task_status(task_address: str) -> dict:
    return get_adapter().get_task_status(task_address)


def get_task_result(task_address: str) -> dict | None:
    return get_adapter().get_task_result(task_address)


def cancel_task_onchain(task_address: str):
    get_adapter().cancel_task(task_address)


def resolve_dataset_url(r2_key: str) -> str:
    """Resolve a dataset R2 key to a publicly accessible URL.

    In mock mode, returns a placeholder.
    In local mode, generates a presigned URL (24h expiry).
    In real mode, generates a presigned URL (24h expiry)
    so the OGPU provider can download the dataset.
    """
    from app.config import settings
    from app.services import storage_service

    if settings.ogpu_adapter == "mock":
        return f"r2://mock-dataset/{r2_key}"

    # Local and real mode: generate presigned URL (24h expiry)
    return storage_service.presigned_url(r2_key, expires_in=86400)
