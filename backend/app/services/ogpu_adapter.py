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
from typing import Optional


@dataclass
class AxolotlConfig:
    """Configuration for a fine-tuning Axolotl task."""
    base_model: str
    dataset_url: str
    preset: str          # fast, balanced, quality
    adapter: str         # lora, qlora
    output_bucket: str


def get_preset_params(preset: str) -> dict:
    """Convert preset name to Axolotl training parameters."""
    presets = {
        "fast": {"num_epochs": 1, "learning_rate": 2e-4, "batch_size": 4},
        "balanced": {"num_epochs": 2, "learning_rate": 1e-4, "batch_size": 4},
        "quality": {"num_epochs": 3, "learning_rate": 5e-5, "batch_size": 8},
    }
    return presets.get(preset, presets["balanced"])


def build_task_config(axolotl: AxolotlConfig) -> dict:
    """Build the config dict for an OGPU task."""
    params = get_preset_params(axolotl.preset)
    return {
        "function_name": "finetune",
        "data": {
            "base_model": axolotl.base_model,
            "dataset_url": axolotl.dataset_url,
            "preset": axolotl.preset,
            "adapter": axolotl.adapter,
            "num_epochs": params["num_epochs"],
            "learning_rate": params["learning_rate"],
            "batch_size": params["batch_size"],
            "output_bucket": axolotl.output_bucket,
        },
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
