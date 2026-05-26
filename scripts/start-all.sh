#!/bin/bash
# Start all app services: backend, worker, frontend
set -e

cd "$(dirname "$0")/.."
LOG_DIR="$PWD/logs"
mkdir -p "$LOG_DIR"

# Kill anything on port 8000 and 3000
if fuser 8000/tcp >/dev/null 2>&1; then
  echo "=> Killing existing process on port 8000..."
  fuser -k 8000/tcp
  sleep 1
fi
if fuser 3000/tcp >/dev/null 2>&1; then
  echo "=> Killing existing process on port 3000..."
  fuser -k 3000/tcp
  sleep 1
fi

echo "=> Starting all services..."
echo ""

# Backend (background, log to file)
cd backend
source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --reload --port 8000 > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
cd ..

# Celery Worker (background, log to file)
cd backend
celery -A app.tasks.celery_app worker --loglevel=info > "$LOG_DIR/worker.log" 2>&1 &
WORKER_PID=$!
cd ..

# Frontend (background, log to file)
cd frontend
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for startup
sleep 4

echo "=> Services started (PIDs: backend=$BACKEND_PID worker=$WORKER_PID frontend=$FRONTEND_PID)"
echo ""
echo "   Backend : http://127.0.0.1:8000"
echo "   Worker  : Celery (logs en logs/worker.log)"
echo "   Frontend: http://127.0.0.1:3000"
echo ""
echo "   Ver logs en vivo: tail -f logs/backend.log"
echo "                     tail -f logs/worker.log"
echo "                     tail -f logs/frontend.log"
echo ""
echo "   Parar todo: kill $BACKEND_PID $WORKER_PID $FRONTEND_PID"
echo ""
echo "--- Backend (ultimas lineas) ---"
tail -5 "$LOG_DIR/backend.log"
echo ""
echo "--- Worker (ultimas lineas) ---"
tail -5 "$LOG_DIR/worker.log"
echo ""
echo "--- Frontend (ultimas lineas) ---"
tail -5 "$LOG_DIR/frontend.log"
