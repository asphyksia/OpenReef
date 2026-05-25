# OpenReef MVP

Simple, affordable AI fine-tuning on decentralized GPU infrastructure (OpenGPU Network).

## Stack

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLAlchemy (async)
- **Database**: PostgreSQL 16
- **Queue**: Celery + Redis (for polling/status updates)
- **Compute**: OpenGPU Network (on-chain escrow + decentralized providers)
- **Training**: Axolotl (LoRA / QLoRA) — runs on provider nodes via OGPU Source
- **Payments**: Stripe (credits) + OGPU escrow (on-chain for jobs)
- **Storage**: Cloudflare R2

## Quick start

```bash
# 1. Copy and configure env
cp .env.example .env
# Edit .env with your values (DB, OGPU private key, Stripe keys, R2 creds)

# 2. Start infrastructure
docker compose up postgres redis -d

# 3. Run migrations
cd backend
alembic upgrade head

# 4. Start backend
uvicorn app.main:app --reload --port 8000

# 5. Start worker (polls OGPU chain for job status)
celery -A app.tasks.celery_app worker --loglevel=info

# 6. Start frontend (in another terminal)
cd frontend
npm install
npm run dev
```

## Architecture

```
Frontend (Next.js)
      ↓
Backend API (FastAPI)
      ↓
PostgreSQL  ←→ Redis/Celery (poller)
      ↓
OGPU SDK (on-chain)
      ↓
┌─ Escrow locked ──────────────────────────────────────┐
│                                                      │
│  OGPU Source (Axolotl Docker) ← Providers register   │
│       ↓                                              │
│  OGPU Task (fine-tune config) ← Providers compete    │
│       ↓                                              │
│  Provider runs training in Docker on GPU             │
│       ↓                                              │
│  Response submitted on-chain → escrow released       │
│                                                      │
└──────────────────────────────────────────────────────┘
      ↓
Output artifact in R2
```

## OGPU Integration

OpenReef uses the OpenGPU Network SDK (`ogpu`) to:

1. **Publish a Source** — defines the Axolotl Docker environment, hardware requirements (NVIDIA GPU), and delivery method (FirstResponse). Published once, reused for all jobs.
2. **Publish Tasks** — each confirmed job becomes an on-chain Task with payment locked in escrow.
3. **Poll for status** — Celery worker polls chain every 30s, maps OGPU statuses to our job statuses, and updates the database.
4. **Retrieve results** — after finalization, the result data (output path on R2) is fetched from the on-chain response.

### OGPU Task lifecycle mapping

| OGPU Status | OpenReef Job Status | Action |
|-------------|---------------------|--------|
| `new` | `queued` | Task published, waiting for providers |
| `attempted` | `running` | Provider started executing |
| `responded` | `completed` | Result submitted |
| `finalized` | `completed` | Payment released to provider |
| `expired` | `failed` | Deadline passed, refund issued |
| `canceled` | `cancelled` | Client canceled, refund issued |

### OGPU Source configuration

Located in `ogpu-source/`:
- `docker-compose-nvidia.yml` — Docker config for NVIDIA GPUs
- `Dockerfile` — Axolotl + CUDA + OGPU SDK
- `worker.py` — Fine-tuning handler: downloads dataset, builds Axolotl config, runs training, uploads to R2

## MVP Flow

1. Register with email/password
2. Add credits via Stripe
3. Upload a dataset (JSONL/CSV/TXT)
4. System validates dataset
5. Select base model + preset (fast/balanced/quality)
6. Choose LoRA or QLoRA
7. Create job → confirm → charge credits → publish OGPU task
8. Training runs on decentralized provider via OGPU
9. Download resulting model artifact from R2

## Limits

- 1 active job per user
- Max 500 MB per dataset
- Max 100,000 rows per dataset
- Presets only (no custom hyperparameters)

## Support

- [Telegram](https://t.me/openreef)
