# OpenReef

[![Build with Ona](https://ona.com/build-with-ona.svg)](https://app.ona.com/#https://github.com/asphyksia/OpenReef)

**Simple, affordable AI fine-tuning on decentralized GPU infrastructure.**

OpenReef is a web platform built on the [OpenGPU Network](https://opengpu.network) that turns the complex process of fine-tuning AI models into a simple web experience: upload a dataset, pick a model, launch a job, and download the trained adapter. No terminal, no YAML, no headaches.

---

## What it does

OpenReef lets anyone — developers, researchers, students, indie hackers — fine-tune open-source AI models using decentralized GPU providers. You pay only for what you use, with no subscriptions or markup pricing.

**The flow:**

1. Register with email/password
2. Upload a dataset (JSONL, CSV, TXT)
3. Pick a base model and training preset
4. See the estimated cost, confirm, and launch
5. Track progress in real time
6. Download your trained adapter

All compute runs on the decentralized OpenGPU Network — providers with NVIDIA or AMD GPUs execute your training jobs automatically.

---

## Features

### Core
- **Auth** — email/password with httpOnly JWT cookies + CSRF double-submit
- **Datasets** — upload JSONL/CSV/TXT with streaming validation (up to 500 MB, 100k rows) and secure presigned downloads
- **Fine-tuning** — LoRA & QLoRA with 3 presets (Fast, Balanced, Quality) for 1.5B–70B models
- **Job tracking** — 10 states with real-time progress polling and dynamic ETA
- **Payments** — Stripe Checkout + internal USD credits with append-only ledger
- **Refunds** — automatic phase-based refunds (100% pending / 50% queued / 0% running)

### SmartRoute
- **Pre-flight capacity check** — validates provider availability before charging the user
- **Hardware discovery** — reads provider GPU specs (model, VRAM) from OGPU on-chain + IPFS
- **Bitwise environment matching** — correctly handles NVIDIA (2), AMD (4), and combined environments
- **Auto-blocking** — providers with >50% fail rate (min 5 jobs) are automatically blocked
- **Stale job cleanup** — periodic detection of jobs without heartbeat (>5 min) with automatic refund

### Provider Reliability
- **Auto-requeue** — if a provider abandons, the job goes back to queued (max 3 attempts)
- **Full refund** — after max attempts, job fails and user gets 100% refund
- **Reputation tracking** — completed/failed/abandoned counters per provider address
- **Artifact validation** — output verified in storage before marking job completed (existence, min 1 KB)
- **Dynamic timeouts** — per-job limits based on preset + model size (7B fast: 2h, 13B quality: 16h)
- **Heartbeat API** — providers send keepalive pings during training

### Security
- **httpOnly JWT cookies** + CSRF double-submit (no localStorage)
- **SSE-AES256** encryption at rest (conditional — only on non-local endpoints)
- **Presigned URLs** with expiry for all downloads (datasets: 1h, artifacts: 1h)
- **Race condition prevention** with `SELECT ... FOR UPDATE` on critical operations
- **Append-only credit ledger** — balance is always `SUM(amount)`, never a mutable column
- **Stripe webhook idempotency** via `processed_events` table
- **Ownership enforcement** — users only access their own datasets and jobs

### Dataset Intelligence
- **Token estimation** — tiktoken (cl100k_base) with streaming sampling every 10th row
- **Format validation** — JSONL structure, CSV columns, TXT line length
- **Size limits** — 500 MB max, 100k rows max, 4096 tokens per example max

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 + TypeScript + Tailwind CSS |
| Backend | FastAPI + SQLAlchemy 2.0 (async with asyncpg) |
| Database | PostgreSQL 16 (10 Alembic migrations) |
| Queue | Celery + Redis (auto-rescheduling, no beat needed) |
| Compute | OpenGPU Network (mock / local / real adapters) |
| Training | Axolotl (LoRA / QLoRA) with hardware-aware config |
| Payments | Stripe Checkout (credits system) |
| Storage | MinIO (dev) / Cloudflare R2 (prod) — S3-compatible via boto3 |
| Tokenizer | tiktoken (cl100k_base) for dataset token estimation |

---

## Architecture

```
Frontend (Next.js 15)
      ↓  JWT httpOnly cookies + CSRF double-submit
Backend API (FastAPI + SQLAlchemy async)
      ↓                    ↕
PostgreSQL  ←→ Redis/Celery  ←→ MinIO/R2 (S3-compatible)
      ↓
SmartRoute (pre-flight capacity check)
      ↓
Job Orchestrator (Celery task auto-rescheduling)
      ↓
OGPU Adapter (mock dev / local machine / real prod)
      ↓
Axolotl + dataset + base model (hardware-aware: NVIDIA CUDA / AMD ROCm)
      ↓
Output on R2 → user download
```

### OGPU Adapter Pattern

The backend uses a facade (`ogpu_service`) with swappable adapters controlled by a single env var:

| Adapter | Use case | Behavior |
|---|---|---|
| `MockOGPUAdapter` | Development | Simulates full job lifecycle in ~30 seconds |
| `LocalOGPUAdapter` | Local machine | Runs Axolotl directly, detects NVIDIA/AMD/CPU |
| `RealOGPUAdapter` | Production | Uses OGPU SDK v0.2.1 for on-chain task publishing |

Switch: `OGPU_ADAPTER=mock` (default), `local`, or `real`.

---

## OGPU Sources

OpenReef publishes a single source on-chain that supports both NVIDIA and AMD providers through `ImageEnvironments`:

```
sources/
└── finetune/
    ├── docker-compose-nvidia.yml   # NVIDIA CUDA providers
    ├── docker-compose-amd.yml      # AMD ROCm providers
    ├── Dockerfile                  # NVIDIA CUDA image
    ├── Dockerfile.rocm             # AMD ROCm image
    └── worker.py                   # Hardware-aware fine-tune worker
```

### How it works

1. OpenReef publishes the source on-chain with both compose URLs
2. Providers register via `management.opengpu.network/sources` — the Provider App auto-detects their hardware
3. NVIDIA providers get the NVIDIA compose file, AMD providers get the AMD compose file
4. The worker detects hardware at runtime and configures Axolotl automatically:

| Hardware | Precision | Attention | Optimizer |
|---|---|---|---|
| NVIDIA CUDA | bf16 | flash-attention | adamw_bnb_8bit |
| AMD ROCm | fp16 | sdp_attention | adamw_torch |

Compose files are hosted on GitHub raw and verified accessible:
- NVIDIA: `raw.githubusercontent.com/.../docker-compose-nvidia.yml`
- AMD: `raw.githubusercontent.com/.../docker-compose-amd.yml`

---

## Quick start

```bash
# 1. Start infrastructure (PostgreSQL, Redis, MinIO)
./scripts/setup.sh

# 2. Start all services (backend, Celery worker, Next.js frontend)
./scripts/start-all.sh

# 3. Open the app
# Frontend: http://127.0.0.1:3000
# API docs: http://127.0.0.1:8000/docs
# Flower:   http://127.0.0.1:5555

# 4. Stop everything
./scripts/stop-all.sh
```

Manual start (separate terminals):

```bash
# Backend
cd backend && source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

# Celery worker (MUST run from backend/ directory)
cd backend && source .venv/bin/activate
PYTHONPATH=. celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1

# Frontend
cd frontend && npm run dev
```

---

## Project structure

```
OpenReef/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, datasets, jobs, payments, providers, models)
│   │   ├── models/       # SQLAlchemy models (user, dataset, job, credit_ledger, provider, base_model)
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # Business logic (auth, credits, datasets, jobs, OGPU adapters, smart_route, pricing, providers, storage)
│   │   ├── tasks/        # Celery tasks (training lifecycle, stale cleanup)
│   │   ├── config.py     # Environment settings (pydantic-settings)
│   │   ├── database.py   # Async DB engine + session
│   │   ├── dependencies.py # Auth, CSRF
│   │   └── main.py       # FastAPI app, routers, CORS, rate limiting
│   ├── alembic/          # Database migrations (10 migrations)
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages (auth, dashboard, datasets, jobs, credits, new-job)
│   │   ├── lib/          # API client (JWT cookies + CSRF)
│   │   └── types/        # TypeScript interfaces
│   └── package.json
├── sources/              # OGPU source definitions
│   ├── README.md
│   └── finetune/         # Fine-tuning source (NVIDIA + AMD)
│       ├── docker-compose-nvidia.yml
│       ├── docker-compose-amd.yml
│       ├── Dockerfile
│       ├── Dockerfile.rocm
│       └── worker.py
├── scripts/              # Dev helper scripts (setup, start-all, stop-all)
├── docker-compose.yml    # PostgreSQL, Redis, MinIO
├── .env.example
└── .gitignore
```

---

## Limits

| Scope | Limit |
|---|---|
| Active jobs per user | 1 |
| Dataset size | 500 MB |
| Dataset rows | 100,000 |
| Tokens per example | ~4,096 |
| Configuration | Presets only (no custom hyperparameters) |

---

## Support

- [Telegram](https://t.me/openreef)
