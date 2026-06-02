"""OGPU adapter — Protocol, Mock (local dev), and Real (SDK) implementations.

Usage:
    from app.services.ogpu_adapter import get_adapter
    adapter = get_adapter()
    task_id = adapter.publish_finetune_task(source, config)
    status = adapter.get_task_status(task_id)

Switch between mock and real via OGPU_ADAPTER env var:
    OGPU_ADAPTER=mock   (default) — simulates job lifecycle
    OGPU_ADAPTER=real             — uses OGPU SDK on-chain
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.services.pricing import PRESET_PARAMS


@dataclass
class AxolotlConfig:
    """Configuration for a fine-tuning Axolotl task."""
    base_model: str
    dataset_url: str
    preset: str          # fast, balanced, quality
    adapter: str         # lora, qlora
    output_prefix: str   # R2 key prefix, e.g. models/{user_id}/{job_id}
    upload_url: str = ""  # presigned PUT URL for artifact upload
    param_count: int = 0  # model size in billions, for batch size adjustment


def get_preset_params(preset: str) -> dict:
    """Convert preset name to Axolotl training parameters."""
    return PRESET_PARAMS.get(preset, PRESET_PARAMS["balanced"])


def build_task_config(axolotl: AxolotlConfig) -> dict:
    """Build the config dict for an OGPU task."""
    params = get_preset_params(axolotl.preset)
    data = {
        "base_model": axolotl.base_model,
        "dataset_url": axolotl.dataset_url,
        "preset": axolotl.preset,
        "adapter": axolotl.adapter,
        "num_epochs": params["num_epochs"],
        "learning_rate": params["learning_rate"],
        "batch_size": params["batch_size"],
        "param_count": axolotl.param_count,
        "output_prefix": axolotl.output_prefix,
    }
    if axolotl.upload_url:
        data["upload_url"] = axolotl.upload_url
    return {
        "function_name": "finetune",
        "data": data,
    }


class OGPUAdapter(ABC):
    """Protocol for OGPU Network operations."""

    @abstractmethod
    def get_source_address(self) -> str:
        """Return the fine-tuning source address."""
        ...

    @abstractmethod
    def publish_task(self, source_address: str, config: dict, payment: float) -> str:
        """Publish a training task. Returns a task identifier."""
        ...

    @abstractmethod
    def get_task_status(self, task_id: str) -> dict:
        """Get current task status.

        Returns: {
            "status_name": "new" | "attempted" | "responded" | "finalized" | "expired" | "canceled",
            "attempter_count": int,
            "attempter_address": str | None,      # first provider to attempt the task
            "attempt_timestamps": list[int],      # unix timestamps of attempts
            "duration_seconds": float | None,     # time from first to last attempt
            "winning_provider": str | None,       # provider who completed the task
            "expiry_time": int | None,            # unix timestamp when task expires
            "time_remaining_seconds": int | None, # seconds until expiry
        }
        """
        ...

    @abstractmethod
    def get_task_result(self, task_id: str) -> dict | None:
        """Retrieve result data for a completed task."""
        ...

    @abstractmethod
    def cancel_task(self, task_id: str) -> None:
        """Cancel a task (best effort)."""
        ...
