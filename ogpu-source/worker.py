"""OGPU Source worker — runs inside the provider's container.

Receives a fine-tuning task from OGPU, runs Axolotl training,
uploads the result to R2, and returns the output path.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import ogpu.service
from pydantic import BaseModel


class FineTuneInput(BaseModel):
    base_model: str
    dataset_url: str
    preset: str
    adapter: str
    num_epochs: int = 2
    learning_rate: float = 1e-4
    batch_size: int = 4
    output_bucket: str = ""


class FineTuneOutput(BaseModel):
    status: str
    output_key: str | None = None
    error: str | None = None


@ogpu.service.init()
def load_model():
    ogpu.service.logger.info("OpenReef fine-tune worker initialized")


def _download_dataset(url: str, target: Path) -> Path:
    """Download dataset from R2 (or public URL) to local path."""
    if url.startswith("http://") or url.startswith("https://"):
        import urllib.request
        urllib.request.urlretrieve(url, target)
    elif url.startswith("r2://"):
        # In production, use boto3 + presigned URL
        # For now, the dataset is already accessible via HTTP
        raise ValueError(f"R2 URLs not yet supported: {url}")
    else:
        raise ValueError(f"Unknown dataset URL scheme: {url}")
    return target


def _build_axolotl_config(job_input: FineTuneInput, config_dir: Path) -> str:
    """Generate an Axolotl YAML config from the job parameters."""
    adapter_cfg = "qlora" if job_input.adapter == "qlora" else "lora"

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
qlora: {job_input.adapter == "qlora"}
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
optimizer: adamw_bnb_8bit
lr_scheduler: cosine
learning_rate: {job_input.learning_rate}

train_on_inputs: false
max_grad_norm: 1.0
weight_decay: 0.0
bf16: true
tf32: true

logging_steps: 10
save_steps: 100
save_total_limit: 1
warmup_steps: 10
"""
    config_path = config_dir / "axolotl.yml"
    config_path.write_text(config)
    return str(config_path)


def _upload_to_r2(local_dir: Path, output_bucket: str, job_id: str) -> str:
    """Upload the trained adapter to R2."""
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("R2_ENDPOINT_URL", ""),
        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY", ""),
        config=Config(signature_version="s3v4"),
    )

    bucket = output_bucket or "openreef-models"
    r2_key = f"{job_id}/adapter/"

    for f in Path(local_dir).rglob("*"):
        if f.is_file():
            rel_path = str(f.relative_to(local_dir))
            client.upload_file(
                str(f),
                bucket,
                f"{r2_key}{rel_path}",
            )
    return f"s3://{bucket}/{r2_key}"


@ogpu.service.expose(timeout=7200)
def finetune(data: FineTuneInput) -> FineTuneOutput:
    """Execute the fine-tuning job."""
    ogpu.service.logger.info(f"Starting fine-tune: {data.base_model} / {data.preset} / {data.adapter}")

    work_dir = Path("/workspace")
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Download dataset
        ogpu.service.logger.info("Downloading dataset...")
        dataset_path = _download_dataset(data.dataset_url, work_dir / "dataset.jsonl")

        # 2. Build Axolotl config
        ogpu.service.logger.info("Building Axolotl config...")
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

        # 4. Upload result to R2
        ogpu.service.logger.info("Uploading trained adapter to R2...")
        output_dir = work_dir / "output"
        output_key = _upload_to_r2(output_dir / "adapter", data.output_bucket, "job-placeholder")

        ogpu.service.logger.info(f"Training complete. Output: {output_key}")
        return FineTuneOutput(status="completed", output_key=output_key)

    except subprocess.TimeoutExpired:
        return FineTuneOutput(status="failed", error="Training exceeded timeout (2 hours)")
    except Exception as e:
        ogpu.service.logger.exception("Training failed")
        return FineTuneOutput(status="failed", error=str(e))


if __name__ == "__main__":
    ogpu.service.start()
