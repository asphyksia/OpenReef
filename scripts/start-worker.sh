#!/bin/bash
# Start Celery worker
set -e

cd "$(dirname "$0")/../backend"
source .venv/bin/activate

echo "=> Starting Celery worker..."
celery -A app.tasks.celery_app worker --loglevel=info
