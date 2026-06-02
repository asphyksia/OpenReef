"""Local OGPU adapter — executes fine-tuning directly on the local machine.

Detects hardware (NVIDIA CUDA vs AMD ROCm vs CPU) and adjusts Axolotl
configuration accordingly. Jobs run as subprocesses managed via Redis state.

Usage:
    OGPU_ADAPTER=local uvicorn app.main:app --reload
"""

import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

import redis

from app.config import settings
from app.services.ogpu_adapter import OGPUAdapter
from app.services import storage_service

logger = logging.getLogger(__name__)

# Redis key prefix for local job state
_LOCAL_JOB_PREFIX = "local_training:"

# Timing for local job lifecycle simulation (seconds)
# These are used while the subprocess is starting up
_LOCAL_ATTEMPTED_AFTER = 5
_LOCAL_RESPONDED_AFTER = 10  # subprocess started, training in progress
_LOCAL_FINALIZED_AFTER = 0   # finalized when subprocess exits


def detect_device() -> str:
    """Detect the available compute device."""
    try:
        import torch
        if torch.cuda.is_available():
            if torch.version.hip is not None:
                return "amd_rocm"
            elif torch.version.cuda is not None:
                return "nvidia_cuda"
    except ImportError:
        pass
    return "cpu"


def build_axolotl_overrides(device_type: str) -> dict:
    """Build Axolotl config overrides based on detected hardware."""
    if device_type == "amd_rocm":
        return {
            "bf16": False,
            "fp16": True,
            "tf32": False,
            "sdp_attention": True,
            "flash_attention": False,
        }
    elif device_type == "nvidia_cuda":
        return {
            "bf16": True,
            "fp16": False,
            "tf32": True,
            "flash_attention": True,
            "sdp_attention": False,
        }
    else:
        return {
            "bf16": False,
            "fp16": False,
            "fp32": True,
            "sdp_attention": True,
        }


def _get_redis() -> redis.Redis:
    """Get a Redis connection for local job state."""
    return redis.from_url(settings.redis_url, decode_responses=True)


def _job_key(task_id: str) -> str:
    return f"{_LOCAL_JOB_PREFIX}{task_id}"


class LocalOGPUAdapter(OGPUAdapter):
    """Executes fine-tuning locally as a subprocess."""

    def get_source_address(self) -> str:
        return "ogpu-source-local"

    def publish_task(self, source_address: str, config: dict, payment: float) -> str:
        task_id = f"local-task-{uuid.uuid4().hex[:12]}"
        device_type = detect_device()

        job_state = {
            "task_id": task_id,
            "config": json.dumps(config),
            "device_type": device_type,
            "status": "new",
            "created_at": str(time.time()),
            "pid": "",
            "log_file": "",
            "output_dir": "",
            "error": "",
        }

        r = _get_redis()
        r.hset(_job_key(task_id), mapping=job_state)
        r.expire(_job_key(task_id), 86400 * 7)  # 7 day TTL

        # Launch the training subprocess
        self._launch_training(task_id, config, device_type)

        return task_id

    def _launch_training(self, task_id: str, config: dict, device_type: str):
        """Launch the local training subprocess."""
        from app.services.local_training import launch_training_subprocess

        work_dir = Path("/tmp/openreef_training") / task_id
        work_dir.mkdir(parents=True, exist_ok=True)

        log_file = str(work_dir / "training.log")
        output_dir = str(work_dir / "output")

        try:
            pid = launch_training_subprocess(
                task_id=task_id,
                config=config,
                device_type=device_type,
                work_dir=str(work_dir),
                log_file=log_file,
                output_dir=output_dir,
            )

            r = _get_redis()
            r.hset(_job_key(task_id), mapping={
                "pid": str(pid),
                "log_file": log_file,
                "output_dir": output_dir,
                "status": "attempted",
            })
            logger.info("Launched training subprocess %d for task %s", pid, task_id)
        except Exception as e:
            logger.exception("Failed to launch training for task %s", task_id)
            r = _get_redis()
            r.hset(_job_key(task_id), mapping={
                "status": "failed",
                "error": str(e),
            })

    def get_task_status(self, task_id: str) -> dict:
        r = _get_redis()
        key = _job_key(task_id)
        state = r.hgetall(key)

        if not state:
            raise ValueError(f"Unknown local task: {task_id}")

        created_at = float(state["created_at"])
        current_status = state.get("status", "new")
        pid = state.get("pid", "")
        error = state.get("error", "")

        # Check if subprocess is still running
        if pid and current_status in ("attempted", "responded"):
            process_alive = False
            try:
                os.kill(int(pid), 0)  # Signal 0 = check if exists
                # Check for zombie process (state Z in /proc/{pid}/stat)
                with open(f"/proc/{pid}/stat", "r") as f:
                    stat_content = f.read()
                    # stat format: pid (comm) state ...
                    state_char = stat_content.split(")")[1].strip().split()[0]
                    process_alive = state_char != "Z"  # Z = zombie
            except (OSError, ValueError, FileNotFoundError, IndexError):
                process_alive = False

            if not process_alive:
                # Process exited — check if artifact is available
                output_dir = state.get("output_dir", "")
                has_artifact = False
                if output_dir:
                    from pathlib import Path
                    output_path = Path(output_dir)
                    has_artifact = bool(list(output_path.glob("**/*.safetensors")) or list(output_path.glob("**/pytorch_model.bin")))

                if has_artifact:
                    current_status = "finalized"
                else:
                    # Process died without producing an artifact (e.g. OOM, crash)
                    current_status = "failed"
                    if not state.get("error"):
                        r.hset(key, "error", "Training process exited without producing an adapter file (possible OOM or crash)")
                r.hset(key, "status", current_status)

        expiry_time = int(created_at) + 86400  # 24h expiry
        time_remaining = expiry_time - int(time.time())

        return {
            "status_name": current_status,
            "attempter_count": 1 if current_status != "new" else 0,
            "attempter_address": "local-machine",
            "attempt_timestamps": [int(created_at) + _LOCAL_ATTEMPTED_AFTER],
            "duration_seconds": None,
            "winning_provider": "local-machine" if current_status == "responded" else None,
            "expiry_time": expiry_time,
            "time_remaining_seconds": max(time_remaining, 0),
        }

    def get_task_result(self, task_id: str) -> dict | None:
        r = _get_redis()
        key = _job_key(task_id)
        state = r.hgetall(key)

        if not state:
            return None

        current_status = state.get("status", "new")
        if current_status not in ("responded", "finalized"):
            return None

        # Check if we already stored the artifact
        output_r2_key = state.get("output_r2_key", "")
        if output_r2_key:
            r.hset(key, "status", "finalized")
            return {
                "output_key": output_r2_key,
                "status": "completed",
                "adapter_type": state.get("adapter_type", "lora"),
                "base_model": state.get("base_model", "unknown"),
            }

        # Subprocess finished — upload artifact to R2
        output_dir = state.get("output_dir", "")
        if not output_dir or not Path(output_dir).exists():
            return None

        # Find the adapter file
        adapter_file = self._find_adapter_file(output_dir)
        if adapter_file is None:
            return None

        config = json.loads(state.get("config", "{}"))
        data = config.get("data", {})
        job_id = data.get("job_id", task_id)
        user_id = data.get("user_id", "local")

        output_r2_key = f"models/{user_id}/{job_id}/adapter.safetensors"

        try:
            file_size = os.path.getsize(adapter_file)
            with open(adapter_file, "rb") as f:
                storage_service.upload_bytes(
                    data=f.read(),
                    key=output_r2_key,
                    content_type="application/octet-stream",
                )

            r.hset(key, mapping={
                "output_r2_key": output_r2_key,
                "status": "finalized",
                "adapter_type": data.get("adapter", "lora"),
                "base_model": data.get("base_model", "unknown"),
            })

            logger.info("Uploaded adapter to %s (%d bytes)", output_r2_key, file_size)
            return {
                "output_key": output_r2_key,
                "status": "completed",
                "adapter_type": data.get("adapter", "lora"),
                "base_model": data.get("base_model", "unknown"),
            }
        except Exception as e:
            logger.exception("Failed to upload adapter for task %s", task_id)
            r.hset(key, mapping={
                "status": "failed",
                "error": f"Upload failed: {e}",
            })
            return None

    def _find_adapter_file(self, output_dir: str) -> str | None:
        """Find the adapter file in the output directory."""
        output_path = Path(output_dir)

        # Look for adapter-merged or adapter_model.safetensors
        patterns = [
            "**/adapter_model.safetensors",
            "**/adapter_merged.safetensors",
            "**/*.safetensors",
            "**/pytorch_model.bin",
        ]

        for pattern in patterns:
            files = list(output_path.glob(pattern))
            if files:
                return str(files[0])

        # Check for checkpoint directory
        checkpoints = list(output_path.glob("checkpoint-*"))
        if checkpoints:
            for ckpt in checkpoints:
                files = list(ckpt.glob("*.safetensors"))
                if files:
                    return str(files[0])

        return None

    def cancel_task(self, task_id: str) -> None:
        r = _get_redis()
        key = _job_key(task_id)
        state = r.hgetall(key)

        if not state:
            return

        pid = state.get("pid", "")
        if pid:
            try:
                pid_int = int(pid)
                os.kill(pid_int, 15)  # SIGTERM
                logger.info("Sent SIGTERM to training process %d", pid_int)
            except (OSError, ValueError):
                pass

        r.hset(key, mapping={
            "status": "canceled",
        })
