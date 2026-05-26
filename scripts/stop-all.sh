#!/bin/bash
# Stop all app services started by start-all.sh
set -e

# Kill by port
echo "=> Stopping backend (port 8000)..."
fuser -k 8000/tcp 2>/dev/null || true

echo "=> Stopping frontend (port 3000)..."
fuser -k 3000/tcp 2>/dev/null || true

# Kill celery workers (they don't bind to ports)
echo "=> Stopping celery workers..."
pkill -f "celery -A app.tasks.celery_app" 2>/dev/null || true

echo "=> Done."
