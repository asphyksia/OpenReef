<div align="center">

[![Build with Ona](https://ona.com/build-with-ona.svg)](https://app.ona.com/#https://github.com/asphyksia/OpenReef)

# OpenReef

**Fine-tune open-source AI models. No terminal. No YAML. No GPU required.**

Built on [OpenGPU Network](https://opengpu.network) · Decentralized compute · Pay only what you use

[![CI](https://img.shields.io/github/actions/workflow/status/asphyksia/OpenReef/test.yml?branch=main&label=CI&style=flat-square&color=01696f)](https://github.com/asphyksia/OpenReef/actions)
[![Tests](https://img.shields.io/badge/tests-115%20passing-01696f?style=flat-square)](https://github.com/asphyksia/OpenReef/actions)
[![Docker](https://img.shields.io/badge/docker-cuda%20%7C%20rocm-01696f?style=flat-square&logo=docker&logoColor=white)](https://github.com/asphyksia/OpenReef/pkgs/container/finetune-worker)
[![Python](https://img.shields.io/badge/python-3.12-01696f?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-01696f?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

</div>

---

## What is OpenReef?

OpenReef is a web platform that turns fine-tuning open-source AI models into a simple four-step experience. Upload a dataset, pick a model, confirm the cost, and download your trained adapter. All compute runs on the decentralized [OpenGPU Network](https://opengpu.network) — no cloud accounts, no GPU setup, no subscriptions.

**Target audience:** indie developers, researchers, students, and small teams who want to work with open-source models without paying enterprise infrastructure prices.

---

## How it works

```
  Upload dataset        Pick model + preset     Confirm & launch
  (JSONL/CSV/TXT)  →   (1.5B–70B, LoRA/QLoRA)  →  (see price first)
         ↓
  SmartRoute finds an available GPU provider on OGPU
         ↓
  Axolotl runs training — hardware-aware (NVIDIA CUDA / AMD ROCm)
         ↓
  Download your trained adapter (presigned URL, secure)
```

Job states: `pending` → `validating` → `queued` → `provisioning` → `running` → `checkpointing` → `completed`

Automatic failover: if a provider drops, the job requeues (max 3 attempts). If all fail, 100% refund.

---

## Pricing

| Model | Preset | Est. time | Price |
|-------|--------|-----------|-------|
| 7B | Fast | ~1h | $0.53 |
| 7B | Balanced | ~2h | $1.05 |
| 7B | Quality | ~4h | $2.10 |
| 13B | Fast | ~1h | $1.05 |
| 13B | Balanced | ~2h | $2.10 |
| 13B | Quality | ~4h | $4.20 |

40–70% cheaper than centralized alternatives. Provider gets 70%, platform keeps 25%, 5% goes to a refund buffer.

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | FastAPI + SQLAlchemy 2.0 async (asyncpg) |
| Database | PostgreSQL 16 — 12 Alembic migrations |
| Queue | Celery + Redis — auto-rescheduling + Beat for maintenance |
| Training | Axolotl (LoRA / QLoRA) — hardware-aware config generation |
| Compute | OpenGPU Network SDK v0.2.1 (mock / local / real adapters) |
| Storage | MinIO (dev) / Cloudflare R2 (prod) — same code, different endpoint |
| Payments | Stripe Checkout + internal USD credit ledger (append-only) |
| CI/CD | GitHub Actions — PostgreSQL + Redis services, 115 tests |
| Production | Docker Compose + Gunicorn + Nginx + deploy script |

---

## Architecture

```
Frontend (Next.js 15 + shadcn/ui)
      ↓  httpOnly JWT cookies + CSRF double-submit
Backend API (FastAPI + SQLAlchemy async)
      ↓                          ↕
PostgreSQL  ←→  Redis / Celery  ←→  MinIO / Cloudflare R2
      ↓
SmartRoute — pre-flight capacity check (VRAM, provider reputation, availability)
      ↓
Job Orchestrator — Celery task with auto-rescheduling
      ↓
OGPU Adapter — mock (dev) / local (machine) / real (on-chain)
      ↓
Axolotl + dataset + base model
Hardware-aware: NVIDIA (bf16 + flash-attn) / AMD ROCm (fp16 + sdp-attn)
      ↓
Output → R2 / MinIO → presigned download URL
```

### OGPU Adapter Pattern

Three swappable adapters, one env var:

| Adapter | `OGPU_ADAPTER=` | Behavior |
|---------|-----------------|----------|
| `MockOGPUAdapter` | `mock` (default) | Full lifecycle simulation in ~30s, no OGPU connection |
| `LocalOGPUAdapter` | `local` | Runs Axolotl directly on the host machine, auto-detects hardware |
| `RealOGPUAdapter` | `real` | OGPU SDK v0.2.1 — publishes on-chain tasks with $OGPU escrow |

---

## Features

### Core
- **Auth** — email/password, httpOnly JWT cookies, CSRF double-submit, email verification (Resend)
- **Datasets** — streaming upload + validation (JSONL/CSV/TXT, 500 MB max, 100k rows), token estimation via tiktoken
- **Fine-tuning** — LoRA & QLoRA, 3 presets (Fast / Balanced / Quality), 1.5B–70B models
- **Job tracking** — 10 states, real-time polling, dynamic ETA
- **Payments** — Stripe Checkout, internal USD credits, append-only ledger, phase-based refunds

### SmartRoute
- Pre-flight capacity check — validates provider availability **before** charging the user
- Hardware discovery — reads GPU specs (model, VRAM) from OGPU on-chain + IPFS
- Bitwise environment matching — correctly handles NVIDIA (env 2), AMD (env 4), and combined
- Auto-blocking — providers with >50% fail rate (min 5 jobs) are automatically excluded

### Provider Reliability
- Auto-requeue — if a provider drops, job goes back to queued (max 3 attempts, then full refund)
- Reputation tracking — completed / failed / abandoned counters per provider address
- Artifact validation — output verified in storage before marking job completed (existence + min 1 KB)
- Dynamic timeouts — `7B fast: 2h`, `13B quality: 16h`
- Zombie detection — detects crashed training processes and handles them gracefully
- Heartbeat API — providers send keepalive pings during training

### Security
- httpOnly JWT cookies + CSRF double-submit (no localStorage)
- `hmac.compare_digest()` for all secret comparisons (timing-safe)
- `yaml.safe_dump()` for Axolotl config generation (injection-safe)
- `SELECT ... FOR UPDATE` on all critical financial operations (race condition prevention)
- Append-only credit ledger — balance is always `SUM(amount)`, never a mutable column
- Stripe webhook idempotency via `processed_events` table
- SSRF protection — URL validation + private IP blocking for artifact downloads
- SSE-AES256 encryption at rest (conditional, non-local endpoints only)
- Ownership enforcement — users only access their own datasets and jobs
- Rate limiting on all mutation endpoints (auth, payments, jobs, datasets, providers)

### Admin & Analytics
- Health endpoints — `/health` (basic), `/health/ready` (infrastructure checks, returns 503 on failure)
- Admin metrics — `/admin/metrics` (usage stats, bearer-protected)
- Job metrics CSV export — `/admin/job-metrics` (anonymized data for pricing & efficiency analysis)

---

## OGPU Sources

OpenReef registers a single source on-chain supporting both NVIDIA and AMD providers via `ImageEnvironments`:

```
sources/
└── finetune/
    ├── Dockerfile                  # NVIDIA CUDA image
    ├── Dockerfile.rocm             # AMD ROCm image
    ├── docker-compose-nvidia.yml   # Compose for NVIDIA providers
    ├── docker-compose-amd.yml      # Compose for AMD providers
    └── worker.py                   # Hardware-aware training worker
```

The worker auto-detects hardware at runtime and adjusts Axolotl config automatically:

| Hardware | Precision | Attention | Optimizer |
|----------|-----------|-----------|-----------|
| NVIDIA CUDA | bf16 | flash-attention | paged_adamw_8bit |
| AMD ROCm | fp16 | sdp_attention | adamw_torch |

Docker images published to GHCR with `pull_policy: always` — providers always pull the latest image:
- `ghcr.io/asphyksia/finetune-worker:cuda-latest`
- `ghcr.io/asphyksia/finetune-worker:rocm-latest`

---

## Quick Start

```bash
# 1. Start infrastructure (PostgreSQL, Redis, MinIO)
./scripts/setup.sh

# 2. Start all services (backend, Celery worker, Next.js frontend)
./scripts/start-all.sh

# 3. Open
#   Frontend:  http://127.0.0.1:3000
#   API docs:  http://127.0.0.1:8000/docs
#   Flower:    http://127.0.0.1:5555

# 4. Run tests
./scripts/test.sh

# 5. Stop everything
./scripts/stop-all.sh
```

<details>
<summary>Manual start (separate terminals)</summary>

```bash
# Infrastructure
docker compose up -d postgres redis minio

# Backend
cd backend && source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

# Celery worker
cd backend && source .venv/bin/activate
PYTHONPATH=. celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1

# Frontend
cd frontend && npm run dev
```

</details>

---

## Production Deploy

```bash
# 1. Copy and fill in production environment variables
cp .env.prod.example .env.prod
# Edit .env.prod with real values (R2, Stripe, JWT secret, etc.)

# 2. Deploy all services
./scripts/deploy.sh deploy

# 3. Check status
./scripts/deploy.sh status

# 4. View logs
./scripts/deploy.sh logs backend

# 5. Stop everything
./scripts/deploy.sh stop
```

Includes: PostgreSQL, Redis, Backend (Gunicorn + 4 Uvicorn workers), Celery Worker, Celery Beat, Frontend (standalone), Nginx (reverse proxy + rate limiting + SSL ready).

---

## Become a Provider

Have a GPU? Earn $OGPU tokens by running fine-tuning jobs.

→ [Provider Onboarding Guide](docs/provider-onboarding.md)

---

## Project Structure

```
OpenReef/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (auth, datasets, jobs, payments, providers, models, health)
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── services/       # Business logic (auth, credits, jobs, OGPU adapters, smart_route, pricing, storage)
│   │   ├── tasks/          # Celery tasks (training lifecycle, stale cleanup, maintenance)
│   │   ├── config.py       # Environment settings (pydantic-settings)
│   │   ├── database.py     # Async DB engine + session factory
│   │   ├── dependencies.py # Auth + CSRF middleware
│   │   └── main.py         # FastAPI app, routers, CORS, rate limiting
│   ├── alembic/            # 12 database migrations
│   ├── tests/              # 115 tests (API, services, tasks, health)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js pages (auth, dashboard, datasets, jobs, credits, new-job)
│   │   ├── lib/            # API client (JWT cookies + CSRF)
│   │   ├── components/     # shadcn/ui components
│   │   └── types/          # TypeScript interfaces
│   └── package.json
├── sources/
│   └── finetune/           # OGPU source — NVIDIA + AMD workers
├── scripts/                # Dev + deploy helpers (setup, start-all, stop-all, test, deploy)
├── nginx/                  # Nginx config (reverse proxy + rate limiting + SSL)
├── docker-compose.yml      # Dev infrastructure (PostgreSQL, Redis, MinIO)
├── docker-compose.prod.yml # Production compose
├── .github/workflows/      # CI: test.yml + docker-images.yml
├── pyproject.toml          # Project config + pytest settings
└── .env.example
```

---

## Limits

| Scope | Limit |
|-------|-------|
| Active jobs per user | 1 |
| Dataset size | 500 MB |
| Dataset rows | 100,000 |
| Tokens per example | ~4,096 |
| Job retries | 3 (2 requeues) |
| Configuration | Presets only — no custom hyperparameters |

---

## Roadmap

### Done
- ✅ Fine-tuning with LoRA/QLoRA for 1.5B–70B models
- ✅ SmartRoute pre-flight capacity check
- ✅ Hardware-aware worker (NVIDIA CUDA + AMD ROCm)
- ✅ Multi-environment OGPU source (single source, two compose files)
- ✅ Provider reliability system (auto-requeue, reputation, artifact validation, zombie detection)
- ✅ Stripe payments + append-only credit ledger + phase-based refunds
- ✅ Token estimation with tiktoken (streaming, every 10th row)
- ✅ Email verification (Resend API)
- ✅ Frontend redesign (shadcn/ui + persistent dark mode)
- ✅ Production Docker Compose + Nginx + deploy script
- ✅ CI/CD — GitHub Actions, 115 tests, PostgreSQL + Redis services
- ✅ Docker images in GHCR (`cuda-latest`, `rocm-latest`)
- ✅ Health endpoints + admin metrics (bearer-protected)
- ✅ Security hardening (timing-safe comparisons, YAML injection prevention, SSRF fixes, CORS restrictions)
- ✅ Job metrics CSV export for pricing & efficiency analysis

### Planned
- 🟡 **Unsloth integration** — faster training, less VRAM (NVIDIA single-GPU)
- 🟡 **Quantize source** — GGUF, GPTQ, AWQ (NVIDIA + AMD + CPU)
- 🟡 **Convert source** — format conversion (safetensors → GGUF, MLX, EXL2)
- 🟡 **Wallet login** — Sign-In with Ethereum (SIWE)
- 🟡 **OGPU payments** — direct $OGPU token payment with 10% discount
- 🟡 **Event-driven polling** — replace Celery polling with `ogpu.events` watchers
- 🟢 **Community Hub** — public model and dataset sharing
- 🟢 **Dataset Lab** — synthetic generation, cleaning, annotation
- 🟢 **Model Playground** — quick testing, A/B comparison, serverless endpoints

---

## Support

- [Telegram](https://t.me/openreef) — announcements + community support
- [API docs](http://127.0.0.1:8000/docs) — interactive Swagger UI (local)
