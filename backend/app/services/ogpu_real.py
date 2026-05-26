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

# SDK v0.2.1 typed errors for granular handling
from ogpu.types import (
    InsufficientBalanceError,
    SourceInactiveError,
    TaskAlreadyFinalizedError,
    MissingSignerError,
    IPFSGatewayError,
    IPFSFetchError,
)


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
        """Use task.snapshot() for a single batch RPC call instead of separate get_status + get_num_attempts."""
        _ensure_chain()
        task = Task(task_id)
        snap = task.snapshot()

        # Get first attempter address for provider tracking
        attempters = task.get_attempters()
        first_attempter = attempters[0] if attempters else None

        # Get attempt timestamps for duration tracking
        timestamps = task.get_attempt_timestamps()
        duration_seconds = (timestamps[-1] - timestamps[0]) if len(timestamps) >= 2 else None

        return {
            "status_name": snap.status.name.lower(),
            "attempter_count": snap.attempt_count,
            "attempter_address": first_attempter,
            "attempt_timestamps": timestamps,
            "duration_seconds": duration_seconds,
            "winning_provider": snap.winning_provider,
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
            receipt = cancel_task_sdk(task_id)
            # receipt.tx_hash and receipt.gas_used available for audit
        except (TaskAlreadyFinalizedError, SourceInactiveError):
            pass  # Task already done or source inactive
        except (MissingSignerError, IPFSGatewayError) as e:
            # Log but don't fail — cancel is best-effort
            import logging
            logging.getLogger(__name__).warning("Cancel failed: %s", e)
        except Exception:
            pass  # Task may already be finalized
