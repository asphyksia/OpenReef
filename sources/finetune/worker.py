"""OGPU Source worker — runs inside the provider's container.

Receives a fine-tuning task from OGPU, detects the available hardware
(NVIDIA CUDA or AMD ROCm), runs Axolotl training with hardware-specific
configuration, and returns the trained adapter via presigned PUT URL or base64.

Hardware detection is automatic — the same worker.py works on both
NVIDIA and AMD providers without modification.
"""

import base64
import json
import os
import subprocess
from pathlib import Path

import ogpu.service
import requests
from pydantic import BaseModel


class FineTuneInput(BaseModel):
    base_model: str
    dataset_url: str
    preset: str
    adapter: str
    num_epochs: int = 2
    learning_rate: float = 1e-4
    batch_size: int = 4
    output_prefix: str = ""
    upload_url: str = ""  # presigned PUT URL for artifact upload


class FineTuneOutput(BaseModel):
    status: str
    output_key: str | None = None
    adapter_base64: str | None = None
    error: str | None = None


def _detect_device() -> str:
    """Detect the available compute device.

    Returns:
        "nvidia_cuda" if NVIDIA GPU with CUDA is available.
        "amd_rocm" if AMD GPU with ROCm is available.
        "cpu" if no GPU is detected.
    """
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


def _get_device_config(device: str) -> dict:
    """Return Axolotl config overrides for the detected device."""
    if device == "amd_rocm":
        return {
            "bf16": "false",
            "fp16": "true",
            "tf32": "false",
            "flash_attention": "false",
            "sdp_attention": "true",
            "optimizer": "adamw_torch",
        }
    elif device == "nvidia_cuda":
        return {
            "bf16": "true",
            "fp16": "false",
            "tf32": "true",
            "flash_attention": "true",
            "sdp_attention": "false",
            "optimizer": "adamw_bnb_8bit",
        }
    else:
        # CPU fallback — very slow, debug only
        return {
            "bf16": "false",
            "fp16": "false",
            "tf32": "false",
            "flash_attention": "false",
            "sdp_attention": "true",
            "optimizer": "adamw_torch",
        }


@ogpu.service.init()
def load_model():
    device = _detect_device()
    ogpu.service.logger.info(
        "OpenReef fine-tune worker initialized — device: %s", device
    )


def _download_dataset(url: str, target: Path) -> Path:
    """Download dataset from R2 (or public URL) to local path."""
    if url.startswith("http://") or url.startswith("https://"):
        import urllib.request
        urllib.request.urlretrieve(url, target)
    elif url.startswith("r2://"):
        raise ValueError(f"R2 URLs require presigned URLs: {url}")
    else:
        raise ValueError(f"Unknown dataset URL scheme: {url}")
    return target


def _build_axolotl_config(job_input: FineTuneInput, config_dir: Path) -> str:
    """Generate an Axolotl YAML config from the job parameters.

    Automatically adjusts precision, attention mechanism, and optimizer
    based on the detected hardware (NVIDIA CUDA vs AMD ROCm).

    QLoRA is automatically converted to LoRA on AMD providers because
    bitsandbytes does not have stable ROCm binaries for all versions.
    """
    device = _detect_device()
    hw = _get_device_config(device)

    # QLoRA requires bitsandbytes which is only reliably available on NVIDIA
    # Fall back to LoRA on AMD providers to avoid runtime failures
    adapter = job_input.adapter
    if adapter == "qlora" and device == "amd_rocm":
        ogpu.service.logger.warning(
            "QLoRA requested on AMD ROCm — falling back to LoRA "
            "(bitsandbytes ROCm support is version-dependent and fragile)"
        )
        adapter = "lora"

    adapter_cfg = "qlora" if adapter == "qlora" else "lora"

    config = f"""
base_model: {job_input.base_model}
base_model_config: {job_input.base_model}
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

datasets:
  - path: /workspace/dataset.jsonl
    type: jsonl
    field_messages:
      - role: user
        content: instruction
      - role: assistant
        content: output

dataset_prepared_path: /workspace/prepared
val_set_size: 0.0
output_dir: /workspace/output

sequence_len: 2048
sample_packing: true
eval_sample_packing: false
pad_to_sequence_len: true

{adapter_cfg}: true
qlora: {adapter == "qlora"}
lora_r: 32
lora_alpha: 64
lora_dropout: 0.05
lora_target_linear: true
lora_target_modules:
  - q_proj
  - v_proj
  - k_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj

gradient_accumulation_steps: 2
micro_batch_size: {job_input.batch_size}
num_epochs: {job_input.num_epochs}
optimizer: {hw['optimizer']}
lr_scheduler: cosine
learning_rate: {job_input.learning_rate}

train_on_inputs: false
max_grad_norm: 1.0
weight_decay: 0.0
bf16: {hw['bf16']}
fp16: {hw['fp16']}
tf32: {hw['tf32']}
flash_attention: {hw['flash_attention']}
sdp_attention: {hw['sdp_attention']}

logging_steps: 10
save_steps: 100
save_total_limit: 1
warmup_steps: 10
"""
    config_path = config_dir / "axolotl.yml"
    config_path.write_text(config)
    return str(config_path)


def _find_adapter_file(output_dir: Path) -> Path | None:
    """Find the adapter safetensors file in the output directory.

    Searches recursively for adapter_model.safetensors, adapter_merged.safetensors,
    or any *.safetensors file. Returns the first match found.
    """
    # Priority order: specific names first, then any safetensors
    priority_names = ["adapter_model.safetensors", "adapter_merged.safetensors"]

    for name in priority_names:
        for f in output_dir.rglob(name):
            if f.is_file():
                return f

    # Fallback: any safetensors file
    for f in output_dir.rglob("*.safetensors"):
        if f.is_file():
            return f

    return None


def _encode_adapter_base64(adapter_path: Path, max_size_bytes: int = 100 * 1024 * 1024) -> str | None:
    """Read adapter file and encode as base64.

    Returns None if the file is too large (>100MB) to encode safely.
    """
    file_size = adapter_path.stat().st_size
    if file_size > max_size_bytes:
        ogpu.service.logger.warning(
            "Adapter file too large for base64 encoding: %.1f MB (limit: %.0f MB)",
            file_size / 1024 / 1024, max_size_bytes / 1024 / 1024,
        )
        return None

    with open(adapter_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _upload_via_presigned_url(adapter_path: Path, upload_url: str, max_size_bytes: int = 500 * 1024 * 1024) -> None:
    """Upload the adapter file to R2 using a presigned PUT URL.

    No R2 credentials needed — the URL is pre-authorized by the backend.

    Args:
        adapter_path: Path to the adapter safetensors file.
        upload_url: Presigned PUT URL from the backend.
        max_size_bytes: Maximum file size (default 500 MB).
    """
    file_size = adapter_path.stat().st_size
    if file_size > max_size_bytes:
        raise ValueError(
            f"Adapter file too large: {file_size / 1024 / 1024:.1f} MB "
            f"(limit: {max_size_bytes / 1024 / 1024:.0f} MB)"
        )

    with open(adapter_path, "rb") as f:
        resp = requests.put(upload_url, data=f, timeout=300)
        resp.raise_for_status()

    ogpu.service.logger.info(
        "Uploaded adapter to R2 via presigned URL: %d bytes", file_size
    )


@ogpu.service.expose(timeout=7200)
def finetune(data: FineTuneInput) -> FineTuneOutput:
    """Execute the fine-tuning job.

    Automatically detects hardware and configures Axolotl accordingly.
    Returns the adapter as base64 (for small adapters) or uploads to R2
    and returns the output key.
    """
    device = _detect_device()
    ogpu.service.logger.info(
        "Starting fine-tune: %s / %s / %s (device: %s)",
        data.base_model, data.preset, data.adapter, device,
    )

    work_dir = Path("/workspace")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Download dataset
        ogpu.service.logger.info("Downloading dataset...")
        dataset_path = _download_dataset(data.dataset_url, work_dir / "dataset.jsonl")

        # 2. Build Axolotl config (hardware-aware)
        ogpu.service.logger.info("Building Axolotl config for %s...", device)
        config_path = _build_axolotl_config(data, work_dir)

        # 3. Run Axolotl training
        ogpu.service.logger.info("Running Axolotl training...")
        result = subprocess.run(
            [
                "accelerate", "launch", "-m", "axolotl.cli.train",
                config_path,
            ],
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hours max
        )

        if result.returncode != 0:
            ogpu.service.logger.error(f"Training failed: {result.stderr}")
            return FineTuneOutput(status="failed", error=result.stderr[:500])

        # 4. Find and return the adapter
        ogpu.service.logger.info("Locating trained adapter...")
        output_dir = work_dir / "output"
        adapter_path = _find_adapter_file(output_dir)

        if adapter_path is None:
            ogpu.service.logger.error("No adapter safetensors file found in %s", output_dir)
            return FineTuneOutput(status="failed", error="No adapter file found after training")

        ogpu.service.logger.info("Found adapter: %s (%.1f MB)", adapter_path, adapter_path.stat().st_size / 1024 / 1024)

        # Try to encode as base64 first (for small adapters <100MB)
        adapter_b64 = _encode_adapter_base64(adapter_path)
        if adapter_b64:
            ogpu.service.logger.info("Returning adapter as base64 (%.1f MB encoded)", len(adapter_b64) / 1024 / 1024)
            return FineTuneOutput(status="completed", adapter_base64=adapter_b64)

        # Fallback: upload via presigned PUT URL for larger adapters
        if not data.upload_url:
            ogpu.service.logger.error("No upload_url provided for large adapter upload")
            return FineTuneOutput(status="failed", error="No upload URL provided for artifact upload")

        ogpu.service.logger.info("Adapter too large for base64, uploading via presigned URL...")
        _upload_via_presigned_url(adapter_path, data.upload_url)
        ogpu.service.logger.info("Training complete. Artifact uploaded to R2 via presigned URL.")
        return FineTuneOutput(status="completed")

    except subprocess.TimeoutExpired:
        return FineTuneOutput(status="failed", error="Training exceeded timeout (2 hours)")
    except Exception as e:
        ogpu.service.exception("Training failed")
        return FineTuneOutput(status="failed", error=str(e))


if __name__ == "__main__":
    ogpu.service.start()
