"""OGPU service — thin wrapper around the adapter for backward compatibility.

All callers should use this module. It delegates to either the mock or real adapter
based on the OGPU_ADAPTER env var.
"""

from app.services.ogpu_factory import get_adapter
from app.services.ogpu_adapter import AxolotlConfig, build_task_config, get_preset_params
from app.services.artifact_validation import validate_artifact


def get_finetune_source_address() -> str:
    return get_adapter().get_source_address()


def publish_finetune_task(
    source_address: str,
    config: dict,
    payment_ogpu_wei: int,
    expiry_minutes: int = 120,
) -> str:
    # payment_ogpu_wei is already in the right unit for both adapters
    return get_adapter().publish_task(source_address, config, payment_ogpu_wei)


def get_task_status(task_address: str) -> dict:
    return get_adapter().get_task_status(task_address)


def get_task_result(task_address: str) -> dict | None:
    return get_adapter().get_task_result(task_address)


def cancel_task_onchain(task_address: str):
    get_adapter().cancel_task(task_address)
