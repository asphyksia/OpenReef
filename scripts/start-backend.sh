#!/bin/bash
# Start FastAPI backend
set -e

cd "$(dirname "$0")/../backend"
source .venv/bin/activate

# Kill anything on port 8000
if fuser 8000/tcp >/dev/null 2>&1; then
  echo "=> Killing existing process on port 8000..."
  fuser -k 8000/tcp
  sleep 1
fi

echo "=> Starting backend on port 8000..."
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
