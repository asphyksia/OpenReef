# OpenReef

Simple, affordable AI fine-tuning on decentralized GPU infrastructure (OpenGPU Network).

**Status:** MVP complete — verified end-to-end in mock mode. Ready for production pending OGPU container build.

## What it does

OpenReef turns the complex process of fine-tuning AI models into a simple web experience: upload a dataset, pick a model, launch a job, and download the trained adapter. No terminal, no YAML, no headaches. All compute runs on the decentralized OpenGPU Network.

## Features

- **Auth** — email/password with httpOnly JWT cookies + CSRF double-submit
- **Datasets** — upload JSONL/CSV/TXT with streaming validation (up to 500 MB, 100k rows) and secure presigned downloads
- **Fine-tuning** — LoRA & QLoRA with 3 presets (Fast, Balanced, Quality) for 7B–70B models
- **Job tracking** — 10 states with real-time progress polling and dynamic ETA
- **Payments** — Stripe Checkout + internal USD credits with append-only ledger
- **Refunds** — automatic phase-based refunds (100% pending / 50% queued / 0% running)
- **Provider reliability** — auto-requeue on failure (max 3 attempts), provider reputation tracking, heartbeat & cancel API
- **Artifact validation** — output verified in storage before marking job completed (existence, min 1 KB size)
- **Dynamic timeouts** — per-job limits based on preset + model size (7B fast: 2h, 13B quality: 16h)
- **Lazy stale-job detection** — zombie jobs auto-failed on read with full refund
- **Idempotency** — confirm_job and run_job are safe against double-click and task re-delivery
- **OGPU SDK v0.2.1 aligned** — snapshot polling, typed errors, vault balance checks, winner tracking
- **Storage** — MinIO (dev) / Cloudflare R2 (prod), swappable via env var, SSE-AES256 at rest

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 + TypeScript + Tailwind CSS |
| Backend | FastAPI + SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 |
| Queue | Celery + Redis (auto-rescheduling, no beat needed) |
| Compute | OpenGPU Network (adapter pattern: mock dev / real prod) |
| Training | Axolotl (LoRA / QLoRA) |
| Payments | Stripe Checkout (credits system) |
| Storage | MinIO (dev) / Cloudflare R2 (prod) — S3-compatible via boto3 |

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

## Architecture

```
Frontend (Next.js 15)
      ↓  JWT httpOnly cookies + CSRF double-submit
Backend API (FastAPI + SQLAlchemy async)
      ↓                    ↕
PostgreSQL  ←→ Redis/Celery  ←→ MinIO/R2 (S3-compatible)
      ↓
Job Orchestrator (Celery task auto-rescheduling)
      ↓
OGPU Adapter (mock dev / real prod)
      ↓
Axolotl + dataset + base model
      ↓
Output on R2 → user download
```

## OGPU Adapter Pattern

The backend uses a facade (`ogpu_service`) with swappable adapters controlled by a single env var:

| Adapter | Use case | Behavior |
|---|---|---|
| `MockOGPUAdapter` | Development | Simulates full job lifecycle in ~30 seconds (`new → attempted → responded → finalized`) |
| `RealOGPUAdapter` | Production | Uses OGPU SDK v0.2.1 for on-chain task publishing, IPFS result retrieval, and vault balance checks |

Switch: `OGPU_ADAPTER=mock` (default) or `OGPU_ADAPTER=real`.

### Mock mode (current default)

In mock mode, the full flow works end-to-end without real OGPU infrastructure:
- Jobs publish, progress through states, and complete in ~30s
- Dummy artifacts (2 KB) are created in MinIO and validated
- Stripe is bypassed — use `/api/payments/dev-add-credits` to add credits
- Perfect for development, testing, and demos

### Production mode

To switch to real OGPU compute, you need:
1. A Docker container with `@ogpu.service.expose()` that runs Axolotl fine-tuning
2. The docker-compose file hosted at a public HTTPS URL (`OGPU_COMPOSE_URL`)
3. `CLIENT_PRIVATE_KEY` and `OGPU_SOURCE_ADDRESS` in `.env`
4. Set `OGPU_ADAPTER=real`

## MVP Flow

1. Register with email/password
2. Add credits via Stripe (or auto-added in dev mode)
3. Upload a dataset (JSONL/CSV/TXT) — validated on upload
4. Select base model + preset (fast / balanced / quality)
5. Choose LoRA or QLoRA
6. See estimated cost → confirm job → charge credits
7. Training runs on decentralized provider via OGPU
8. Track progress in real time with dynamic ETA
9. Download resulting model adapter from R2 (presigned URL, 1h expiry)

## Provider Reliability

> **Note:** The Provider HTTP API (`/api/providers/`) is mock/hybrid-only. In production, provider identity is authenticated on-chain via OGPU wallet — no HTTP secrets needed.

- **Auto-requeue**: if a provider abandons, the job goes back to queued (max 3 attempts total)
- **Full refund**: after max attempts, job fails and user gets 100% refund
- **Reputation tracking**: completed/failed/abandoned counters per provider address
- **Artifact validation**: output checked before marking completed — invalid output triggers failure + refund
- **Dynamic timeouts**: per-job limits based on preset + model size
- **Heartbeat API**: providers send keepalive pings during training
- **Cancel API**: providers can voluntarily cancel a job (triggers requeue or refund)

## Security

- **httpOnly JWT cookies** + CSRF double-submit (no localStorage)
- **SSE-AES256** encryption at rest (conditional — only on non-local endpoints)
- **Presigned URLs** with expiry for all downloads (datasets: 1h, artifacts: 1h, dataset for provider: 24h)
- **Race condition prevention** with `SELECT ... FOR UPDATE` on confirm_job, cancel_job, and credit charges
- **Append-only credit ledger** — balance is always `SUM(amount)`, never a mutable column
- **Stripe webhook idempotency** via `processed_events` table
- **Ownership enforcement** — users only access their own datasets and jobs

## Limits

| Scope | Limit |
|---|---|
| Active jobs per user | 1 |
| Dataset size | 500 MB |
| Dataset rows | 100,000 |
| Tokens per example | ~4,096 (estimated) |
| Configuration | Presets only (no custom hyperparameters) |

## Project structure

```
OpenReef/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (auth, datasets, jobs, payments, providers, models)
│   │   ├── models/       # SQLAlchemy models (user, dataset, job, credit_ledger, provider, base_model)
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # Business logic (auth, credits, datasets, jobs, OGPU adapters, pricing, providers, storage)
│   │   ├── tasks/        # Celery tasks (training lifecycle with auto-rescheduling)
│   │   ├── config.py     # Environment settings (pydantic-settings)
│   │   ├── database.py   # Async DB engine + session
│   │   ├── dependencies.py # Auth, CSRF
│   │   └── main.py       # FastAPI app, routers, CORS, rate limiting
│   ├── alembic/          # Database migrations (7 migrations)
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages (auth, dashboard, datasets, jobs, credits, new-job)
│   │   ├── lib/          # API client (JWT cookies + CSRF)
│   │   └── types/        # TypeScript interfaces
│   └── package.json
├── scripts/              # Dev helper scripts (setup, start-all, stop-all)
├── docker-compose.yml    # PostgreSQL, Redis, MinIO
└── .env.example
```

## Support

- [Telegram](https://t.me/openreef)
