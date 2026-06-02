#!/usr/bin/env bash
# OpenReef Test Runner
# Usage: ./scripts/test.sh [options]
#
# Options:
#   --all          Run all tests (default)
#   --api          Run API tests only
#   --services     Run service tests only
#   --tasks        Run task tests only
#   --coverage     Run with coverage report
#   --no-db        Skip DB setup (assumes PostgreSQL already running)
#   --help         Show this help
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

# Detect Python — prefer .venv if available, fallback to system python
if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    PYTHON="$BACKEND_DIR/.venv/bin/python"
    ALEMBIC="$BACKEND_DIR/.venv/bin/alembic"
else
    PYTHON="${PYTHON:-python3}"
    ALEMBIC="${ALEMBIC:-alembic}"
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}>>>${NC} $1"; }

# Parse arguments
TEST_PATH="backend/tests"
COVERAGE=""
SKIP_DB=false

for arg in "$@"; do
    case "$arg" in
        --api)       TEST_PATH="backend/tests/test_api" ;;
        --services)  TEST_PATH="backend/tests/test_services" ;;
        --tasks)     TEST_PATH="backend/tests/test_tasks" ;;
        --coverage)  COVERAGE="--cov=app --cov-report=term-missing --cov-report=html" ;;
        --no-db)     SKIP_DB=true ;;
        --help)
            head -10 "$0" | tail -9
            exit 0
            ;;
        *)
            log_error "Unknown option: $arg"
            exit 1
            ;;
    esac
done

# ─── PostgreSQL setup ───
if [ "$SKIP_DB" = false ]; then
    log_step "Checking PostgreSQL..."

    # Check if PostgreSQL is already running on test port
    if command -v pg_isready &>/dev/null && pg_isready -h 127.0.0.1 -p 5444 -U postgres -q 2>/dev/null; then
        log_info "PostgreSQL is already running on port 5444"
    elif command -v pg_isready &>/dev/null; then
        log_warn "PostgreSQL not running. Starting with docker compose..."
        docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d postgres
        log_info "Waiting for PostgreSQL to be ready..."
        for i in $(seq 1 30); do
            if pg_isready -h 127.0.0.1 -p 5444 -U postgres -q 2>/dev/null; then
                log_info "PostgreSQL is ready"
                break
            fi
            if [ "$i" -eq 30 ]; then
                log_error "PostgreSQL failed to start after 30s"
                exit 1
            fi
            sleep 1
        done
    else
        log_warn "pg_isready not found — skipping PostgreSQL health check"
        log_info "Assuming PostgreSQL is already running (CI environment)"
    fi

    # Create test database if it doesn't exist
    if command -v psql &>/dev/null; then
        log_step "Setting up test database..."
        PGPASSWORD=postgres psql -h 127.0.0.1 -p 5444 -U postgres -tAc \
            "SELECT 1 FROM pg_database WHERE datname='openreef_test'" | grep -q 1 || \
            PGPASSWORD=postgres psql -h 127.0.0.1 -p 5444 -U postgres -c "CREATE DATABASE openreef_test"

        # Run migrations on test database
        log_step "Running migrations on test database..."
        cd "$BACKEND_DIR"
        DATABASE_URL="postgresql+psycopg2://postgres:postgres@127.0.0.1:5444/openreef_test" \
            "$ALEMBIC" upgrade head 2>/dev/null || true
        cd "$PROJECT_DIR"
    else
        log_warn "psql not found — skipping database setup (tests use Base.metadata.create_all)"
    fi
fi

# ─── Run tests ───
log_step "Running tests: $TEST_PATH (using $PYTHON)"
echo ""

cd "$PROJECT_DIR"
export PYTHONPATH="$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"

$PYTHON -m pytest $TEST_PATH $COVERAGE
RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    log_info "All tests passed!"
else
    log_error "Tests failed with exit code $RESULT"
fi

exit $RESULT
