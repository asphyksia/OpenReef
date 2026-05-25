"""Real OGPU SDK adapter for production use.

Uses the ogpu Python SDK to interact with the OpenGPU Network:
- publish sources on-chain
- publish tasks with escrow
- poll task status
- retrieve results from IPFS
"""

import os
import time

from ogpu.chain import ChainConfig, ChainId
from ogpu.client import publish_source, publish_task, cancel_task as cancel_task_sdk
from ogpu.protocol import Task
from ogpu.types import (
    SourceInfo,
    TaskInfo,
    TaskInput,
    ImageEnvironments,
    DeliveryMethod,
)

from app.services.ogpu_adapter import OGPUAdapter


_OGPU_TESTNET = os.environ.get("OGPU_USE_TESTNET", "true").lower() == "true"
_FINETUNE_SOURCE_ADDRESS = os.environ.get("OGPU_SOURCE_ADDRESS", "")


def _ensure_chain():
    chain = ChainId.OGPU_TESTNET if _OGPU_TESTNET else ChainId.OGPU_MAINNET
    if ChainConfig.chain != chain:
        ChainConfig.set_chain(chain)


class RealOGPUAdapter(OGPUAdapter):
    """Production adapter using the OGPU Python SDK."""

    def get_source_address(self) -> str:
        if _FINETUNE_SOURCE_ADDRESS:
            return _FINETUNE_SOURCE_ADDRESS

        _ensure_chain()

        source_info = SourceInfo(
            name="OpenReef-FineTune",
            description="Axolotl fine-tuning for LoRA/QLoRA adapters",
            imageEnvs=ImageEnvironments(
                nvidia="docker-compose-nvidia.yml"
            ),
            deliveryMethod=DeliveryMethod.FIRST_RESPONSE,
            minPayment=0,
            minAvailableLockup=0,
            maxExpiryDuration=7200,
        )

        source = publish_source(source_info)
        return source.address

    def publish_task(self, source_address: str, config: dict, payment: float) -> str:
        _ensure_chain()

        task_info = TaskInfo(
            source=source_address,
            config=TaskInput(
                function_name=config["function_name"],
                data=config["data"],
            ),
            expiryTime=int(time.time()) + 7200,
            payment=int(payment),
        )

        task = publish_task(task_info)
        return task.address

    def get_task_status(self, task_id: str) -> dict:
        _ensure_chain()
        task = Task(task_id)
        status = task.get_status()
        return {
            "status_name": status.name.lower(),
            "attempter_count": task.get_num_attempts(),
        }

    def get_task_result(self, task_id: str) -> dict | None:
        _ensure_chain()
        task = Task(task_id)
        response = task.get_confirmed_response()
        if response is None:
            return None
        return response.fetch_data()

    def cancel_task(self, task_id: str) -> None:
        _ensure_chain()
        try:
            cancel_task_sdk(task_id)
        except Exception:
            pass  # Task may already be finalized
