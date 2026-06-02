"""Local training subprocess launcher.

Handles downloading datasets, building Axolotl configs adapted to the
detected hardware, and launching the training process.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

logger = logging.getLogger(__name__)

# Local storage directory for training data
_TRAINING_BASE = Path("/tmp/openreef_training")

ALLOWED_ADAPTERS = {"lora", "qlora"}
ALLOWED_DEVICE_TYPES = {"amd_rocm", "nvidia_cuda", "cpu"}


def download_dataset(url: str, output_path: Path) -> Path:
    """Download a dataset from a presigned URL or copy from local MinIO."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if url.startswith("r2://") or url.startswith("http://127.0.0.1") or url.startswith("http://localhost"):
        # Local MinIO — download via HTTP
        if url.startswith("r2://"):
            raise ValueError(f"Cannot download R2 URL in local mode: {url}")
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        # HTTP(S) URL — download directly
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    logger.info("Downloaded dataset to %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path


def build_axolotl_yaml_config(
    base_model: str,
    dataset_path: str,
    device_type: str,
    preset_params: dict,
    adapter_type: str,
    output_dir: str,
    optimizer: str = "adamw_torch",
) -> str:
    """Build an Axolotl YAML config adapted to the hardware.

    Uses yaml.safe_dump() to prevent YAML injection attacks — all values
    are properly serialized as strings/booleans/numbers, never interpolated
    into raw YAML text.
    """
    if adapter_type not in ALLOWED_ADAPTERS:
        raise ValueError(f"Unsupported adapter type: {adapter_type!r}")
    if device_type not in ALLOWED_DEVICE_TYPES:
        raise ValueError(f"Unsupported device type: {device_type!r}")
    if "\n" in base_model or "\r" in base_model:
        raise ValueError("base_model must not contain newlines")

    # Hardware-specific overrides
    if device_type == "amd_rocm":
        bf16 = False
        fp16 = True
        tf32 = False
        flash_attention = False
        sdp_attention = True
    elif device_type == "nvidia_cuda":
        bf16 = True
        fp16 = False
        tf32 = True
        flash_attention = True
        sdp_attention = False
    else:
        bf16 = False
        fp16 = False
        tf32 = False
        flash_attention = False
        sdp_attention = True

    batch_size = int(preset_params.get("batch_size", 1))
    param_count = int(preset_params.get("param_count", 0))

    # Reduce batch size for large models on AMD ROCm to avoid OOM
    if device_type == "amd_rocm":
        if param_count >= 8:
            batch_size = min(batch_size, 1)
        elif param_count >= 7:
            batch_size = min(batch_size, 2)

    gradient_accumulation = max(1, 4 // max(batch_size, 1))

    # Gradient checkpointing: only enable for models >= 7B
    needs_gc = param_count >= 7

    config: dict[str, Any] = {
        "base_model": base_model,
        "model_type": "AutoModelForCausalLM",
        "tokenizer_type": "AutoTokenizer",
        "datasets": [
            {
                "path": dataset_path,
                "type": "completion",
                "field": "text",
            }
        ],
        "bf16": bf16,
        "fp16": fp16,
        "tf32": tf32,
        "flash_attention": flash_attention,
        "sdp_attention": sdp_attention,
        "adapter": adapter_type,
        "lora_r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "lora_target_linear": True,
        "num_epochs": int(preset_params.get("num_epochs", 2)),
        "learning_rate": float(preset_params.get("learning_rate", 2e-4)),
        "micro_batch_size": batch_size,
        "gradient_accumulation_steps": gradient_accumulation,
        "max_seq_length": 512,
        "warmup_ratio": 0.1,
        "output_dir": output_dir,
        "save_strategy": "epoch",
        "save_total_limit": 1,
        "logging_steps": 1,
        "optimizer": optimizer,
        "lr_scheduler": "cosine",
    }

    if needs_gc:
        config["gradient_checkpointing"] = True
        config["gradient_checkpointing_kwargs"] = {"use_reentrant": True}
    else:
        config["gradient_checkpointing"] = False

    return yaml.safe_dump(
        config,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )


def launch_training_subprocess(
    task_id: str,
    config: dict,
    device_type: str,
    work_dir: str,
    log_file: str,
    output_dir: str,
) -> int:
    """Launch the Axolotl training subprocess.

    Returns the PID of the subprocess.
    """
    work_path = Path(work_dir)
    data = config.get("data", {})

    base_model = data.get("base_model", "Qwen/Qwen2.5-1.5B")
    dataset_url = data.get("dataset_url", "")
    adapter_type = data.get("adapter", "lora")
    preset = data.get("preset", "balanced")

    # Get preset params
    from app.services.ogpu_adapter import get_preset_params
    preset_params = get_preset_params(preset)
    preset_params["param_count"] = data.get("param_count", 0)

    # Determine optimizer based on device type
    if device_type == "amd_rocm":
        optimizer = "adamw_torch"  # bitsandbytes not available for ROCm 7.2
    elif device_type == "nvidia_cuda":
        optimizer = "paged_adamw_8bit"
    else:
        optimizer = "adamw_torch"  # CPU fallback

    # Download dataset
    dataset_path = work_path / "dataset.jsonl"
    if dataset_url:
        try:
            download_dataset(dataset_url, dataset_path)
        except Exception as e:
            logger.error("Failed to download dataset from URL: %s", e)
            raise RuntimeError(f"Dataset download failed: {e}. Job cannot proceed without valid dataset.")
    else:
        raise RuntimeError("No dataset URL provided. Job cannot proceed.")

    # Build Axolotl config
    yaml_content = build_axolotl_yaml_config(
        base_model=base_model,
        dataset_path=str(dataset_path),
        device_type=device_type,
        preset_params=preset_params,
        adapter_type=adapter_type,
        output_dir=output_dir,
        optimizer=optimizer,
    )

    config_path = work_path / "axolotl_config.yaml"
    config_path.write_text(yaml_content)
    logger.info("Wrote Axolotl config to %s", config_path)

    # Set environment variables for the subprocess
    env = os.environ.copy()
    env["AXOLOTL_DO_NOT_TRACK"] = "1"

    if device_type == "amd_rocm":
        env["HIP_VISIBLE_DEVICES"] = "0"
        env["HSA_OVERRIDE_GFX_VERSION"] = os.environ.get("HSA_OVERRIDE_GFX_VERSION", "12.0.0")
        env["TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL"] = "1"
    elif device_type == "nvidia_cuda":
        env["CUDA_VISIBLE_DEVICES"] = "0"

    # Build the command — use accelerate launch with axolotl
    cmd = [
        sys.executable, "-m", "axolotl.cli.train",
        str(config_path),
    ]

    logger.info("Launching training: %s", " ".join(cmd))
    logger.info("Device type: %s", device_type)

    # Open log file for stdout/stderr
    log_fh = open(log_file, "w")
    log_fh.write(f"Training config: {json.dumps(data, indent=2)}\n")
    log_fh.write(f"Device type: {device_type}\n")
    log_fh.write(f"Command: {' '.join(cmd)}\n\n")
    log_fh.flush()

    # Launch subprocess
    proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(work_path),
    )

    log_fh.write(f"Subprocess PID: {proc.pid}\n")
    log_fh.flush()
    log_fh.close()

    return proc.pid


