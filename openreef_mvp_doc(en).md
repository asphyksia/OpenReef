# OpenReef — MVP Document

## 1. MVP Objective

The objective of OpenReef's MVP is to validate that there is real demand for a simple, usable, and affordable platform built on OpenGPU Network, focused on the most valuable and clearest use case: **straightforward fine-tuning of small/medium open-source models** on decentralized infrastructure. OpenReef relies on a simple web architecture with a backend API, job queue, and decoupled workers — a fairly common pattern for heavy, asynchronous tasks.

The MVP is not meant to solve the entire roadmap. It aims to demonstrate that a user can register, upload a dataset, launch a basic fine-tune, track progress, download the result, and pay simply — without touching a terminal, YAML, or complex pipelines. Axolotl already offers a direct flow for LoRA and QLoRA from YAML configurations and JSONL-style datasets, making it a reasonable foundation for this initial scope.

## 2. What's NOT included

To keep the MVP small, several elements from the master document are left out or heavily reduced. There will be no fallback to centralized infrastructure; all compute will continue to depend on OGPU. There will also be no complete on-chain escrow system, advanced community earnings, DPO, exotic formats, or complex observability at this stage.

The criterion is simple: if a feature is not necessary for the user to complete the flow "upload data → train → receive model," it gets postponed.

## 3. The problem it solves

Today, fine-tuning an open-source model remains expensive, fragmented, and too technical for many users. Axolotl simplifies part of the training process, but it is still a command-line tool based on configuration files; OpenReef turns that flow into an assisted web experience.

The MVP validates three hypotheses:
- there are users willing to pay for a simpler fine-tuning experience;
- OGPU can serve as a sufficient operational backbone for this type of job;
- the pay-as-you-go model makes sense compared to more expensive centralized alternatives.

## 4. MVP Scope

### Implemented features

The MVP includes the following features, all operational and tested end-to-end:

- **Registration and login** via email and password with basic email verification and JWT sessions.
- **User dashboard** with real-time credit balance, job list with statuses, access to datasets and generated models.
- **Dataset upload** in JSONL, CSV, and TXT with storage on MinIO/R2 (S3-compatible) and presigned URLs for secure downloads.
- **Dataset validation** before training: format, maximum size (500 MB), maximum rows (100,000), minimum columns, and structure.
- **Base model selection** from a curated list of 5 models (2×7B, 3×13B) with documented VRAM requirements.
- **Fine-tuning configuration** through three simple presets: Fast, Balanced, and Quality. These internally translate to Axolotl configurations with controlled parameters.
- **LoRA and QLoRA adapters** supported with automatic Axolotl configuration generation.
- **Two-phase job launch**: first the cost is estimated, then the user confirms and credits are charged. This allows users to see the price before committing funds.
- **Real-time job status tracking** with 10 possible states: pending, validating, queued, provisioning, running, checkpointing, completed, failed, cancelled, refunded.
- **Basic checkpointing** mapped from OGPU when the provider saves intermediate progress.
- **Automatic retry**: if a provider abandons or fails, the job is automatically re-queued with a maximum of 3 attempts. On the third, definitive failure and full refund.
- **Result artifact download** via presigned R2/MinIO URL with configurable expiration.
- **Stripe payments** via internal USD credits. Stripe Checkout integrated with webhooks for async confirmation. In development, an automatic mode bypasses Stripe when keys are placeholder.
- **Refund system** with phase-based policy: 100% if the job never left pending, 50% if already queued but without a provider, 0% if the provider was already working.
- **Provider reputation**: counters of completed, failed, and abandoned jobs per address. Infrastructure ready to filter bad actors in later phases.
- **Telegram support** integrated in the dashboard.
- **Health endpoint** reporting status of PostgreSQL, Redis, and MinIO.

### Postponed features

Left for later phases:

- Wallet login and direct OGPU payments.
- Full Community Hub.
- Full Quantization Lab.
- Full Dataset Lab.
- Serverless API Hosting.
- On-chain escrow.
- Creator earnings.
- AI support.
- Polished provider onboarding.

## 5. Primary use case

The MVP is built around a single strong use case:

1. The user registers with email and password.
2. Uploads a dataset in JSONL, CSV, or TXT.
3. The system automatically validates format, size, and structure.
4. Chooses a compatible base model from the available list.
5. Selects a training preset (Fast, Balanced, or Quality).
6. Sees the estimated cost and confirms the job — credits are charged at that moment.
7. The system publishes the job on OGPU and the user sees progress in real time.
8. If the provider abandons, the system automatically retries with another provider (max 3 attempts).
9. If everything goes well, downloads their LoRA or resulting artifact via a secure link.
10. If the job definitively fails after retries, the balance is automatically refunded.

If this flow works well, the MVP has already demonstrated real utility.

## 6. MVP Architecture

The implemented architecture is simple but robust enough for asynchronous jobs. A FastAPI + Celery + Redis + PostgreSQL stack clearly separates the API, job queue, and worker execution.

### Components

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS.
- **Backend API**: FastAPI with async SQLAlchemy.
- **Database**: PostgreSQL (16).
- **Job queue**: Celery + Redis.
- **Storage**: MinIO in development, Cloudflare R2 in production — swappable via environment variable thanks to the S3-compatible API.
- **Training worker**: Python Celery worker that generates the Axolotl configuration, publishes the job on OGPU, and polls until completion. The worker self-reschedules without needing Celery Beat.
- **Compute infrastructure**: OpenGPU Network, with swappable adapter (mock for development, real SDK for production).
- **Payments**: Stripe Checkout + webhooks + internal credit system.

### Logical architecture

```text
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

No need for complex microservices. The MVP works with a monolithic API/orchestration structure and a separate worker for heavy jobs.

### OGPU adapter pattern

The backend uses a facade (`ogpu_service`) that delegates to swappable adapters via a factory pattern. In development, `MockOGPUAdapter` is used (deterministic simulation based on wall-clock time: a full job completes in ~30 seconds). In production, `RealOGPUAdapter` is used (official OGPU SDK). The switch is controlled by a single environment variable: `OGPU_ADAPTER=mock|real`.

This pattern allows developing and testing the full flow without depending on real OGPU infrastructure, and switching to production without touching code.

## 7. MVP Stack

### Frontend
- Next.js 15
- TypeScript
- Tailwind CSS

### Backend
- FastAPI
- SQLAlchemy 2.0 (async with asyncpg)
- PostgreSQL 16
- Redis 7
- Celery (prefork with psycopg2)

### ML / jobs
- Axolotl for LoRA and QLoRA with JSONL alpaca-style datasets.
- Python workers with auto-rescheduling via `apply_async`.

### Infrastructure
- OpenGPU Network SDK (real adapter)
- Cloudflare R2 (production) / MinIO (development)
- Stripe Checkout + webhooks
- Docker Compose for local development (PostgreSQL, Redis, MinIO)

## 8. What we implemented exactly

### 8.1 Authentication

Implemented:
- email + password with bcrypt;
- basic email verification;
- JWT sessions;
- route protection via frontend middleware.

Wallet login is not included yet.

### 8.2 Dashboard

Implemented:
- real-time credit balance;
- job list with statuses and percentage progress;
- access to uploaded datasets;
- access to generated models with secure download;
- Telegram support link.

### 8.3 Dataset upload

Implemented:
- JSONL, CSV, TXT;
- storage on MinIO/R2 with structure `datasets/{user_id}/{dataset_id}/`;
- presigned URLs for secure download with expiration;
- metadata in database: size, format, row count, validation status.

PDF or more complex parsing is left out.

### 8.4 Dataset validation

Implemented:
- maximum size (500 MB);
- maximum rows (100,000);
- minimum columns per format;
- valid structure (parseable JSONL, CSV with headers, etc.);
- ownership detection: a user can only use their own datasets.

Pending: basic token estimation and compatibility check with the chosen preset.

### 8.5 Fine-tuning

Implemented:
- LoRA and QLoRA;
- 7B and 13B compatible models;
- three simple presets that translate to Axolotl configuration:
  - **Fast**: 1 epoch, lr 2e-4, batch 4 (~1 hour estimated)
  - **Balanced**: 2 epochs, lr 1e-4, batch 4 (~2 hours estimated)
  - **Quality**: 3 epochs, lr 5e-5, batch 8 (~4 hours estimated)

No full configuration freedom. Presets control hyperparameters internally.

### 8.6 SmartRoute MVP

Implemented in its simplest form:
- check minimum job requirements;
- publish task on OGPU with Axolotl configuration;
- state polling until completion or failure;
- automatic retry if the provider abandons.

The mock adapter simulates the full cycle in development: publish → wait for provider → running → completed in ~30 seconds.

### 8.7 Checkpointing and recovery

Implemented:
- `checkpointing` state mapped from OGPU when the provider saves progress;
- if the node crashes or the provider abandons, the job is automatically re-queued;
- maximum 3 attempts (requeue × 2); on the third, definitive failure with full refund to the user;
- provider reputation system: completed, failed, and abandoned jobs tracked per address.

### 8.8 Payments

Implemented:
- internal USD credits with append-only ledger (entries are never modified);
- recharge via Stripe Checkout (payment session with redirect);
- Stripe webhook with guaranteed idempotency (`processed_events` table);
- estimated cost shown before confirming the job;
- charge happens at confirmation time (not at creation);
- phase-based refund policy:
  - `pending`: 100% (money never left the platform);
  - `queued`: 50% (published on OGPU but no provider assigned);
  - `provisioning` or higher: 0% (provider is already working);
- **Dev mode**: when Stripe keys are placeholder, the system adds credits automatically without needing Stripe — ideal for local development and testing.

## 9. Operational limits of the MVP

To avoid breaking the network or the platform, the MVP launches with strict limits.

### Per user
- 1 active job per account.
- daily job limit.
- spending limit if needed.

### Per dataset
- maximum 500 MB.
- maximum 100,000 rows.
- maximum 4,096 tokens per example.

### Per model
- closed list of compatible base models.
- focus on 7B and some 13B if routing allows.

### Per configuration
- presets only, no full custom configuration.

## 10. Minimal versioning

The MVP doesn't need a complex registry, but basic order is necessary.

### Datasets
Each uploaded dataset has:
- `dataset_id`
- name
- date
- size
- format
- validation status
- storage key (MinIO/R2)

### Models
Each result has:
- `job_id`
- base model
- dataset used
- preset applied
- date
- status
- download path on R2

### Providers
Each provider that processes a job is tracked with:
- `address` (on-chain identifier)
- completed, failed, and abandoned jobs
- last activity
- last abandonment (if applicable)

## 11. MVP Security

MVP security is reasonable, not maximalist.

### What we do
- datasets stored on S3-compatible storage with controlled access (presigned URLs with expiration);
- TLS in transit;
- ownership validation: a user can only access their own datasets and jobs;
- race conditions protected with `SELECT ... FOR UPDATE` on critical operations (confirm job, cancel job, charge credits);
- Stripe webhook idempotency with processed event registry;
- Stripe webhook signature validation to prevent forged requests.

### What we don't promise yet
- TEE or advanced hardware isolation;
- perfect security against a malicious provider with deep host control;
- complete cryptographic escrow from day one;
- JWT in httpOnly cookies (currently in localStorage — pending improvement).

## 12. Monitoring and operations

Implemented:
- `/api/health` endpoint reporting status of PostgreSQL, Redis, and MinIO;
- Flower for monitoring Celery workers and queues (port 5555);
- structured backend and worker logs;
- detailed job states with `status_detail` informing the user of specific progress.

OpenTelemetry and a full observability stack are not included yet.

## 13. MVP Support

Simple support:
- Telegram channel for announcements;
- Telegram group for support and community;
- basic moderation.
- direct link in the dashboard footer.

This is sufficient for a private beta or early users.

## 14. Provider onboarding

Perfecting provider onboarding within OpenReef is not an MVP objective. At this stage, the focus is on the user side.

What we have prepared:
- provider API with shared secret authentication;
- heartbeat and cancel-job endpoints;
- reputation system that tracks each provider's behavior;
- documentation to be written when the flow is real and tested with actual providers.

## 15. MVP Technical Roadmap

### Phase A — System foundation ✅ Completed
- frontend and backend repositories;
- email/password auth;
- PostgreSQL + Redis;
- job structure;
- minimal dashboard.

### Phase B — Data and training ✅ Completed
- dataset upload and validation;
- R2/MinIO storage;
- Axolotl config generation;
- worker integration;
- LoRA/QLoRA launch.

### Phase C — Real jobs on OGPU ✅ Completed
- simple node selection via OGPU;
- remote execution with adapter pattern;
- job states with automatic polling;
- basic checkpoints;
- simple recovery with automatic requeue.

### Phase D — Billing and operations ✅ Completed
- Stripe integration with webhooks;
- credit balance with append-only ledger;
- estimated cost before job;
- automatic phase-based refunds;
- minimal monitoring with health endpoint + Flower;
- Telegram as support.

### Phase E — Provider reliability ✅ Completed (Phase 1)
- provider reputation system;
- automatic requeue with 3-attempt limit;
- heartbeat endpoint for providers;
- cancel-job endpoint with refund handling;
- completed/failed/abandoned counters.

### Phase F — Pending
- heartbeat timeout enforcement (cron/beat);
- dynamic timeout per job type;
- artifact validation before marking as completed;
- automatic penalty for providers with poor reputation.

## 16. What we need to build it

### Development
- web frontend;
- backend API;
- ML worker;
- OGPU integration;
- Stripe integration;
- R2/MinIO storage.

### Product
- curated list of initial base models;
- well-defined training presets;
- error and refund policy;
- clear operational limits;
- simple and understandable UI copy.

### Operations
- Stripe account;
- R2 bucket;
- backend deployment;
- Redis/Postgres;
- real OGPU access for testing;
- Telegram group and channel.

## 17. MVP Success Criteria

The MVP will be successful if it demonstrates the following:

- a user can complete an end-to-end fine-tune without touching a terminal;
- the system can execute jobs on OGPU with a reasonable success rate;
- real costs allow maintaining an economic edge over centralized alternatives;
- users understand the product without an excessive learning curve;
- the technical foundation is simple enough to expand later without rebuilding everything.

## 18. Guiding principle

The main rule of the MVP is this: **simple version of everything first; expansion later**.

That means:
- less freedom, more control;
- fewer features, more clarity;
- fewer promises, more reliability;
- less magic, more real working flow.

If the MVP solves the core case of simple fine-tuning on OGPU very well, the rest of the roadmap can be built on top with much more solidity.
