"""Mock OGPU adapter for local development.

Simulates the full OGPU task lifecycle with configurable delays:
  new → attempted → responded → finalized

State is stored in PostgreSQL (job table) via the job_id embedded in task_id.
This makes it work correctly with Celery prefork (multi-process).
"""

import time
import os

from app.services.ogpu_adapter import OGPUAdapter


class MockOGPUAdapter(OGPUAdapter):
    """Simulates OGPU Network with deterministic lifecycle based on elapsed time."""

    # Timing in seconds for the mock lifecycle
    ATTEMPTED_AFTER = 10
    RESPONDED_AFTER = 20
    FINALIZED_AFTER = 30

    def get_source_address(self) -> str:
        return "ogpu-source-mock"

    def publish_task(self, source_address: str, config: dict, payment: float) -> str:
        # Return a deterministic task ID with embedded timestamp
        ts = int(time.time())
        return f"mock-task-{ts}"

    def get_task_status(self, task_id: str) -> dict:
        # Extract timestamp from task_id (mock-task-XXXXXXXXXX)
        try:
            ts_str = task_id.rsplit("-", 1)[1]
            created_at = int(ts_str)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid mock task ID: {task_id}")

        elapsed = time.time() - created_at

        if elapsed >= self.FINALIZED_AFTER:
            return {"status_name": "finalized", "attempter_count": 1}
        elif elapsed >= self.RESPONDED_AFTER:
            return {"status_name": "responded", "attempter_count": 1}
        elif elapsed >= self.ATTEMPTED_AFTER:
            return {"status_name": "attempted", "attempter_count": 1}
        else:
            return {"status_name": "new", "attempter_count": 0}

    def get_task_result(self, task_id: str) -> dict | None:
        # Extract timestamp
        try:
            ts_str = task_id.rsplit("-", 1)[1]
            created_at = int(ts_str)
        except (ValueError, IndexError):
            return None

        elapsed = time.time() - created_at
        if elapsed < self.FINALIZED_AFTER:
            return None

        return {
            "output_key": f"models/mock/{task_id}/adapter/",
            "status": "completed",
            "adapter_type": "lora",
            "base_model": "mock-model",
        }

    def cancel_task(self, task_id: str) -> None:
        # No-op for mock (no actual on-chain task)
        pass
