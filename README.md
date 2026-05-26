# OpenReef

Simple, affordable AI fine-tuning on decentralized GPU infrastructure (OpenGPU Network).

## Features

- **Auth** — email/password with JWT sessions
- **Datasets** — upload JSONL/CSV/TXT with validation and secure presigned downloads
- **Fine-tuning** — LoRA & QLoRA with 3 presets (Fast, Balanced, Quality) for 7B/13B models
- **Job tracking** — 10 states with real-time progress polling
- **Payments** — Stripe Checkout + internal USD credits with append-only ledger
- **Refunds** — automatic phase-based refunds (100%/50%/0%)
- **Provider reliability** — automatic requeue on failure (max 3 attempts), provider reputation tracking
- **Storage** — MinIO (dev) / Cloudflare R2 (prod), swappable via env var

## Stack

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL 16
- **Queue**: Celery + Redis
- **Compute**: OpenGPU Network (adapter pattern: mock dev / real prod)
- **Training**: Axolotl (LoRA / QLoRA)
- **Payments**: Stripe (credits system)
- **Storage**: MinIO / Cloudflare R2 (S3-compatible)

## Quick start

```bash
# 1. Start infrastructure (PostgreSQL, Redis, MinIO)
./scripts/setup.sh

# 2. Start all services (backend, Celery worker, Next.js frontend)
./scripts/start-all.sh

# 3. View logs
tail -f logs/backend.log
tail -f logs/worker.log
tail -f logs/frontend.log

# 4. Stop everything
./scripts/stop-all.sh
```

Manual start (if you prefer separate terminals):

```bash
# Backend
cd backend && source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload --port 8000

# Celery worker
cd backend && source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info

# Frontend
cd frontend && npm run dev
```

Open http://127.0.0.1:3000 to use the app. API docs at http://127.0.0.1:8000/docs.

## Architecture

```
Frontend (Next.js 15)
      ↓
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

The backend uses a facade (`ogpu_service`) with swappable adapters:

| Adapter | Use case | Behavior |
|---------|----------|----------|
| `MockOGPUAdapter` | Development | Simulates full job lifecycle in ~30 seconds |
| `RealOGPUAdapter` | Production | Uses OGPU SDK for on-chain task publishing |

Switch with one env var: `OGPU_ADAPTER=mock` (default) or `OGPU_ADAPTER=real`.

## MVP Flow

1. Register with email/password
2. Add credits via Stripe (or auto-added in dev mode)
3. Upload a dataset (JSONL/CSV/TXT)
4. System validates format, size, and structure
5. Select base model + preset (fast/balanced/quality)
6. Choose LoRA or QLoRA
7. See estimated cost → confirm job → charge credits
8. Training runs on decentralized provider via OGPU
9. Track progress in real time
10. Download resulting model artifact from R2

## Provider Reliability

- **Auto-requeue**: if a provider abandons, the job goes back to queued (max 3 attempts total)
- **Full refund**: after max attempts, job fails and user gets 100% refund
- **Reputation tracking**: completed/failed/abandoned counters per provider address
- **Heartbeat API**: providers send keepalive pings during training
- **Cancel API**: providers can voluntarily cancel a job (triggers requeue or refund)

## Limits

- 1 active job per user
- Max 500 MB per dataset
- Max 100,000 rows per dataset
- Presets only (no custom hyperparameters)

## Project structure

```
backend/app/
├── api/          # FastAPI routers (auth, datasets, jobs, payments, providers)
├── models/       # SQLAlchemy models
├── services/     # Business logic (credits, jobs, OGPU, providers)
├── tasks/        # Celery tasks (training lifecycle)
├── schemas/      # Pydantic request/response models
└── config.py     # Environment settings

frontend/src/
├── app/          # Next.js pages and layouts
├── components/   # React components
└── lib/          # API client, auth helpers

scripts/          # Dev helper scripts
```

## Documentation

- [MVP Document (English)](openreef_mvp_doc(en).md)
- [Documento del MVP (Español)](openreef_mvp_doc(es).md)

## Support

- [Telegram](https://t.me/openreef)
