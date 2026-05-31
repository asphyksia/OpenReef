# OpenReef Fine-Tune Sources

Docker images and compose files for the OpenReef fine-tuning source on OGPU Network.

## Structure

```
sources/finetune/
├── docker-compose-nvidia.yml   # NVIDIA CUDA providers
├── docker-compose-amd.yml      # AMD ROCm providers
├── Dockerfile                  # NVIDIA CUDA image
├── Dockerfile.rocm             # AMD ROCm image
└── worker.py                   # Hardware-aware fine-tune worker
```

## How it works

1. OpenReef publishes a source on-chain with both compose URLs in `ImageEnvironments`.
2. Providers register via `management.opengpu.network/sources` — the Provider App auto-detects their hardware.
3. NVIDIA providers get `docker-compose-nvidia.yml`, AMD providers get `docker-compose-amd.yml`.
4. The worker (`worker.py`) detects hardware at runtime and adjusts Axolotl config automatically:
   - **NVIDIA CUDA**: bf16 + flash-attention + adamw_bnb_8bit
   - **AMD ROCm**: fp16 + sdp_attention + adamw_torch

## Building images

```bash
# NVIDIA
docker buildx build --push -t ghcr.io/openreef/finetune-worker:cuda-latest -f Dockerfile .

# AMD ROCm
docker buildx build --push -t ghcr.io/openreef/finetune-worker:rocm-latest -f Dockerfile.rocm .
```

## Environment variables

| Variable | Description |
|---|---|
| `HF_TOKEN` | HuggingFace token for gated models |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret key |
| `R2_ENDPOINT_URL` | Cloudflare R2 endpoint URL |
| `HSA_OVERRIDE_GFX_VERSION` | AMD ROCm GFX version override (optional) |
