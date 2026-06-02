# OpenReef Provider Onboarding Guide

Become a compute provider on the OpenReef network and earn $OGPU tokens by running fine-tuning jobs.

---

## Overview

OpenReef is an AI fine-tuning platform built on the [OpenGPU Network (OGPU)](https://opengpu.network). As a provider, you contribute GPU compute power to train AI models and earn tokens in return.

**How it works:**
1. You register your GPU on an OpenReef source via the OGPU management dApp
2. The OpenReef worker container runs automatically on your machine
3. Fine-tuning jobs are assigned to you via First-Response matching
4. You earn $OGPU tokens for completed jobs

---

## Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| GPU | NVIDIA GPU with 8GB VRAM | NVIDIA GPU with 16GB+ VRAM |
| VRAM | 8 GB | 16-24 GB |
| RAM | 16 GB | 32 GB |
| Storage | 50 GB free (SSD) | 100 GB NVMe |
| Network | Stable broadband | 100+ Mbps upload |
| OS | Linux (Ubuntu 22.04+) | Linux (Ubuntu 22.04+) |

### GPU Compatibility

**NVIDIA (CUDA):**
- RTX 3060 12GB, RTX 3080, RTX 3090, RTX 4060 Ti 16GB, RTX 4070, RTX 4080, RTX 4090
- A10, A100, H100 (cloud instances)
- Requires CUDA 12.4+ compatible driver

**AMD (ROCm):**
- RX 7900 XTX, RX 7900 XT, RX 7800 XT
- Radeon Pro W7900, W7800
- Requires ROCm 6.0+ (ROCm 7.2+ recommended)

**Note:** QLoRA (8-bit quantization) requires NVIDIA GPUs. AMD providers automatically fall back to LoRA.

---

## Step-by-Step Registration

### 1. Install Prerequisites

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker
docker run hello-world
```

### 2. Set Up OGPU Wallets

You need two wallets:
- **Master Wallet:** Your main wallet for receiving payments
- **Provider Wallet:** Used by the provider container for on-chain interactions

1. Visit [management.opengpu.network](https://management.opengpu.network)
2. Connect or create your Master Wallet
3. Create a Provider Wallet (can be done in the management dApp)
4. Link both wallets (Master ↔ Provider pairing)

### 3. Register on the OpenReef Source

1. Go to [management.opengpu.network](https://management.opengpu.network)
2. Find the **OpenReef Fine-Tune Source**
3. Click **Register** and select your Provider Wallet
4. Select your environment:
   - **NVIDIA (CUDA)** — if you have an NVIDIA GPU
   - **AMD (ROCm)** — if you have an AMD GPU
5. Confirm the registration on-chain

### 4. Start the Provider Container

After registration, the management dApp will provide you with the Docker Compose URL for your environment.

```bash
# NVIDIA providers
curl -O https://raw.githubusercontent.com/Asphyksia/OpenReef/main/sources/finetune/docker-compose-nvidia.yml

# AMD providers
curl -O https://raw.githubusercontent.com/Asphyksia/OpenReef/main/sources/finetune/docker-compose-amd.yml

# Start the worker
docker compose -f docker-compose-nvidia.yml up -d
```

The container will:
- Auto-detect your GPU hardware
- Download required dependencies (Axolotl, PyTorch, model weights)
- Start listening for fine-tuning jobs

### 5. Verify Your Provider is Active

Check the worker logs:

```bash
docker compose -f docker-compose-nvidia.yml logs -f
```

You should see:
```
OpenReef fine-tune worker initialized — device: nvidia_cuda
Waiting for tasks...
```

Your provider should now appear on the OpenReef platform as available.

---

## How Jobs Work

### Job Lifecycle

```
Published → Attempted → Responded → Finalized
  (escrow)    (training)  (upload)    (payment)
```

1. **Published:** A user creates a fine-tuning job on OpenReef
2. **Attempted:** Your worker picks up the job (First-Response matching)
3. **Responded:** Training completes, adapter uploaded to IPFS
4. **Finalized:** Payment is released to your wallet

### What Happens During Training

1. Worker downloads the dataset via presigned URL (no credentials needed)
2. Axolotl runs the fine-tuning with hardware-optimized settings
3. The trained adapter (LoRA weights) is uploaded via presigned PUT URL
4. Worker reports completion on-chain

### Automatic Configuration

The worker auto-detects your hardware and adjusts:

| Hardware | Precision | Attention | Optimizer |
|---|---|---|---|
| NVIDIA CUDA | bf16 | Flash Attention | adamw_bnb_8bit |
| AMD ROCm | fp16 | SDPA Attention | adamw_torch |
| CPU | fp32 | SDPA Attention | adamw_torch |

---

## Earnings

- Payment is in **$OGPU tokens** via OGPU escrow
- Amount depends on job complexity (model size, preset, dataset size)
- Payment is released automatically when the job is finalized on-chain
- Failed or timed-out jobs do not earn payment

### Reputation System

Your provider tracks:
- `completed_count`: Successful jobs
- `failed_count`: Failed jobs
- `abandoned_count`: Jobs that timed out

Providers with >50% fail rate (minimum 5 jobs) are automatically blocked from receiving new jobs.

---

## Troubleshooting

### Worker won't start

```bash
# Check Docker is running
docker ps

# Check GPU is visible
nvidia-smi  # NVIDIA
rocminfo    # AMD

# Check logs
docker compose -f docker-compose-nvidia.yml logs
```

### "No GPU detected"

- **NVIDIA:** Ensure `nvidia-container-toolkit` is installed
  ```bash
  sudo apt install nvidia-container-toolkit
  sudo systemctl restart docker
  ```
- **AMD:** Ensure ROCm drivers are installed
  ```bash
  rocminfo | grep "Name:"
  ```

### Job fails with OOM

- Your GPU doesn't have enough VRAM for the model/preset combination
- The system will auto-requeue to another provider
- Consider registering for smaller models only

### Provider shows as inactive

1. Check the worker container is running: `docker ps`
2. Check heartbeat is being sent (logs should show periodic updates)
3. Restart the container if needed

### Stuck on "attempted"

- The job may be timing out due to large dataset or slow hardware
- Check worker logs for training progress
- If the job exceeds the timeout, it will be marked as failed

---

## Support

- **GitHub Issues:** https://github.com/Asphyksia/OpenReef/issues
- **OGPU Discord:** https://opengpu.network/discord
- **Management dApp:** https://management.opengpu.network

---

## FAQ

**Q: Can I run multiple providers on one machine?**
A: One provider per GPU is recommended. Multi-GPU machines can run one worker per GPU.

**Q: What happens if my machine goes offline during training?**
A: The job will be marked as failed and requeued. Your fail rate will increase.

**Q: Can I choose which jobs to accept?**
A: No. Jobs are assigned automatically via First-Response matching. You cannot cherry-pick jobs.

**Q: Is my GPU data shared publicly?**
A: Only your provider address (wallet) and aggregated stats are visible on-chain. No personal data is shared.

**Q: Can I unregister?**
A: Yes. Simply stop the Docker container. Your provider will be marked inactive after missing heartbeats.
