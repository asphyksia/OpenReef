# OpenReef

AI fine-tuning platform on OpenGPU Network. FastAPI + Next.js 15 + Axolotl + OGPU SDK.

## CRITICAL: Auto-load Context

**ALWAYS load the `openreef` skill at the start of every session:**

```
skill({ name: "openreef" })
```

This contains the complete project memory: architecture, 40+ bug fixes, dev setup, OGPU SDK integration, critical gotchas, and session history.

## Quick Reference

- **Code:** `/home/asphyksia/workspace/OpenReef`
- **Backend:** `backend/` (FastAPI, uvicorn port 8000)
- **Frontend:** `frontend/` (Next.js 15, port 3000)
- **Dev infra:** `docker compose up -d postgres redis minio` (apps run local from `.venv`)
- **User language:** Spanish
