#!/bin/bash
# Run database migrations
set -e

cd "$(dirname "$0")/../backend"
source .venv/bin/activate

echo "=> Running alembic migrations..."
PYTHONPATH=. alembic upgrade head
