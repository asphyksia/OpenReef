"""Real OGPU SDK adapter for production use.

Uses the ogpu Python SDK to interact with the OpenGPU Network:
- publish sources on-chain
- publish tasks with escrow
- poll task status
- retrieve results from IPFS
"""

import logging
import os
import time
from urllib.parse import urlparse
from ipaddress import ip_address, IPv4Address, IPv6Address

import requests
from ogpu.chain import ChainConfig, ChainId
from ogpu.client import publish_source, publish_task, cancel_task as cancel_task_sdk
from ogpu.protocol import Task, vault
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

logger = logging.getLogger(__name__)

_OGPU_TESTNET = os.environ.get("OGPU_USE_TESTNET", "true").lower() == "true"
_FINETUNE_SOURCE_ADDRESS = os.environ.get("OGPU_SOURCE_ADDRESS", "")

# URL to the hosted docker-compose files for the OpenReef Axolotl source
# Must be public HTTPS URLs — providers fetch these to set up their container
_GITHUB_RAW = "https://raw.githubusercontent.com/Asphyksia/OpenReef/main/sources/finetune"

_COMPOSE_URL_NVIDIA = os.environ.get(
    "OGPU_COMPOSE_URL_NVIDIA",
    f"{_GITHUB_RAW}/docker-compose-nvidia.yml",
)
_COMPOSE_URL_AMD = os.environ.get(
    "OGPU_COMPOSE_URL_AMD",
    f"{_GITHUB_RAW}/docker-compose-amd.yml",
)

# SSRF protection: block private, loopback, link-local, and metadata IPs
_BLOCKED_HOSTS = (
    "localhost", "127.0.0.1", "::1", "0.0.0.0",
    "169.254.169.254",  # AWS/GCP metadata
    "metadata.google.internal",
)

def _is_safe_url(url: str) -> bool:
    """Check if a URL is safe to fetch (not SSRF)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        hostname = parsed.hostname or ""
        if hostname in _BLOCKED_HOSTS:
            return False
        # Check if it's a private IP (literal)
        try:
            ip = ip_address(hostname)
            if isinstance(ip, (IPv4Address, IPv6Address)) and (
                ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            ):
                return False
        except ValueError:
            pass  # hostname — resolve DNS and check
            try:
                import socket
                resolved = socket.gethostbyname(hostname)
                ip = ip_address(resolved)
                if isinstance(ip, (IPv4Address, IPv6Address)) and (
                    ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                ):
                    return False
            except Exception:
                return False
        return True
    except Exception:
        return False

MAX_ARTIFACT_DOWNLOAD_BYTES = 500 * 1024 * 1024  # 500 MB


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

        # Check if we already published and cached the address in this process
        if hasattr(self, "_cached_source_address") and self._cached_source_address:
            return self._cached_source_address

        source_info = SourceInfo(
            name="OpenReef-FineTune",
            description="Axolotl fine-tuning for LoRA/QLoRA adapters",
            imageEnvs=ImageEnvironments(
                nvidia=_COMPOSE_URL_NVIDIA,
                amd=_COMPOSE_URL_AMD,
            ),
            deliveryMethod=DeliveryMethod.FIRST_RESPONSE,
            minPayment=0,
            minAvailableLockup=0,
            maxExpiryDuration=7200,
        )

        source = publish_source(source_info)
        self._cached_source_address = source.address
        logger.info(
            "Published new source on-chain: %s — set OGPU_SOURCE_ADDRESS=%s to reuse",
            source.address, source.address,
        )
        return source.address

    def publish_task(self, source_address: str, config: dict, payment: float) -> str:
        _ensure_chain()

        try:
            vault_balance = vault.get_balance_of(source_address)
            if vault_balance < int(payment):
                raise InsufficientBalanceError(
                    f"Vault balance {vault_balance} wei < required payment {payment} wei"
                )
        except InsufficientBalanceError:
            raise
        except Exception as e:
            # Log the failure but proceed — vault contract may not exist
            logger.warning("Could not verify vault balance: %s", e)

        task_info = TaskInfo(
            source=source_address,
            config=TaskInput(
                function_name=config["function_name"],
                data=config["data"],
            ),
            expiryTime=int(time.time()) + 7200,
            payment=int(payment),
        )

        try:
            task = publish_task(task_info)
            return task.address
        except InsufficientBalanceError:
            raise
        except SourceInactiveError as e:
            raise RuntimeError(f"Source {source_address} is inactive. Publish a new source.") from e
        except IPFSGatewayError as e:
            raise RuntimeError(f"IPFS gateway error publishing task: {e}") from e
        except MissingSignerError as e:
            raise RuntimeError("Missing OGPU private key for signing") from e

    def get_task_status(self, task_id: str) -> dict:
        _ensure_chain()
        task = Task(task_id)
        snap = task.snapshot()

        attempters = task.get_attempters()
        first_attempter = attempters[0] if attempters else None
        timestamps = task.get_attempt_timestamps()
        duration_seconds = (timestamps[-1] - timestamps[0]) if len(timestamps) >= 2 else None

        expiry_time = task.get_expiry_time()
        time_remaining = expiry_time - int(time.time()) if expiry_time else None

        return {
            "status_name": snap.status.name.lower(),
            "attempter_count": snap.attempt_count,
            "attempter_address": first_attempter,
            "attempt_timestamps": timestamps,
            "duration_seconds": duration_seconds,
            "winning_provider": snap.winning_provider,
            "expiry_time": expiry_time,
            "time_remaining_seconds": time_remaining,
        }

    def get_task_result(self, task_id: str) -> dict | None:
        _ensure_chain()
        task = Task(task_id)
        response = task.get_confirmed_response()
        if response is None:
            return None
        return response.fetch_data()

    def retrieve_and_store_artifact(self, task_id: str, output_r2_key: str) -> str | None:
        """Bridge: download the model artifact from IPFS and upload to R2.

        The provider uploads their result to IPFS via the OGPU Response mechanism.
        We fetch the IPFS JSON, extract the artifact URL (base64 or IPFS gateway URL),
        download the binary, and upload it to our R2 bucket.

        Returns the R2 key if successful, None if the artifact couldn't be retrieved.
        """
        result = self.get_task_result(task_id)
        if not result or not isinstance(result, dict):
            logger.warning("No result data for task %s", task_id)
            return None

        # The provider's response JSON may contain the artifact in different formats:
        # 1. "adapter_base64" — base64-encoded safetensors (for small LoRA adapters)
        # 2. "adapter_url" — IPFS gateway URL to the binary
        # 3. "output_key" — legacy R2 key (for backward compat / mock mode)
        adapter_base64 = result.get("adapter_base64")
        adapter_url = result.get("adapter_url")

        artifact_bytes = None

        if adapter_base64:
            # Validate base64 string size before decoding to prevent memory exhaustion
            # base64 encodes 3 bytes as 4 chars, so max chars = MAX_BYTES * 4/3
            max_base64_chars = int(MAX_ARTIFACT_DOWNLOAD_BYTES * 4 / 3) + 1024
            if len(adapter_base64) > max_base64_chars:
                logger.error("adapter_base64 too large: %d chars (limit: %d)", len(adapter_base64), max_base64_chars)
                return None

            import base64
            try:
                artifact_bytes = base64.b64decode(adapter_base64)
            except Exception as e:
                logger.error("Failed to decode adapter_base64: %s", e)
                return None

            # Double-check decoded size
            if len(artifact_bytes) > MAX_ARTIFACT_DOWNLOAD_BYTES:
                logger.error("Decoded artifact too large: %d bytes", len(artifact_bytes))
                return None
        elif adapter_url:
            if not _is_safe_url(adapter_url):
                logger.error("SSRF blocked: unsafe artifact URL %s", adapter_url)
                return None
            try:
                resp = requests.get(adapter_url, timeout=300, stream=True)
                resp.raise_for_status()
                artifact_bytes = b""
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > MAX_ARTIFACT_DOWNLOAD_BYTES:
                        logger.error("Artifact download exceeded %d bytes limit", MAX_ARTIFACT_DOWNLOAD_BYTES)
                        return None
                    artifact_bytes += chunk
            except Exception as e:
                logger.error("Failed to download artifact from IPFS: %s", e)
                return None

        if not artifact_bytes:
            logger.warning("No artifact found in result for task %s", task_id)
            return None

        # Upload to R2
        from app.services import storage_service
        storage_service.upload_bytes(artifact_bytes, output_r2_key)
        logger.info("Stored artifact at %s (%d bytes)", output_r2_key, len(artifact_bytes))
        return output_r2_key

    def cancel_task(self, task_id: str) -> None:
        _ensure_chain()
        try:
            receipt = cancel_task_sdk(task_id)
        except (TaskAlreadyFinalizedError, SourceInactiveError):
            pass
        except (MissingSignerError, IPFSGatewayError) as e:
            logger.warning("Cancel failed: %s", e)
        except Exception:
            pass
