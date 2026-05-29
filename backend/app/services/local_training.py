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
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Local storage directory for training data
_TRAINING_BASE = Path("/tmp/openreef_training")


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
    """Build an Axolotl YAML config adapted to the hardware."""
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

    batch_size = preset_params.get("batch_size", 1)
    gradient_accumulation = max(1, 4 // batch_size)

    yaml_config = f"""base_model: {base_model}
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

datasets:
  - path: {dataset_path}
    type: completion
    field: text

# Hardware-specific
bf16: {str(bf16).lower()}
fp16: {str(fp16).lower()}
tf32: {str(tf32).lower()}
flash_attention: {str(flash_attention).lower()}
sdp_attention: {str(sdp_attention).lower()}

# LoRA
adapter: {adapter_type}
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target_linear: true

# Training
num_epochs: {preset_params.get("num_epochs", 2)}
learning_rate: {preset_params.get("learning_rate", 2e-4)}
micro_batch_size: {batch_size}
gradient_accumulation_steps: {gradient_accumulation}
max_seq_length: 512
warmup_ratio: 0.1
gradient_checkpointing: true

# Output
output_dir: {output_dir}
save_strategy: "epoch"
save_total_limit: 1
logging_steps: 1

# Optimizer
optimizer: {optimizer}
lr_scheduler: cosine
"""
    return yaml_config


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
        optimizer = "adamw_torch"  # bitsandbytes not available for ROCm 7.2
    elif device_type == "nvidia_cuda":
        env["CUDA_VISIBLE_DEVICES"] = "0"
        optimizer = "paged_adamw_8bit"

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

    return proc.pid


def _create_placeholder_dataset(path: Path):
    """Create a small placeholder dataset for testing."""
    examples = [
        {"text": "### Instruction: Translate to English: Hola mundo\n### Response: Hello world"},
        {"text": "### Instruction: What is the capital of France?\n### Response: Paris"},
        {"text": "### Instruction: Translate to Spanish: Good morning\n### Response: Buenos días"},
        {"text": "### Instruction: What is 2+2?\n### Response: 4"},
        {"text": "### Instruction: Translate to English: Buenos días\n### Response: Good morning"},
    ]
    with open(path, "w") as f:
        for example in examples:
            f.write(json.dumps(example) + "\n")
    logger.info("Created placeholder dataset at %s (%d examples)", path, len(examples))
