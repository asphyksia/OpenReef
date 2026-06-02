#!/usr/bin/env bash
# OpenReef Production Deploy Script
# Usage: ./scripts/deploy.sh [deploy|stop|logs|restart|status]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env.prod"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_env() {
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error ".env.prod not found!"
        log_info "Copy .env.prod.example to .env.prod and fill in real values:"
        log_info "  cp .env.prod.example .env.prod"
        exit 1
    fi

    # Check required variables
    local required_vars=(
        "POSTGRES_PASSWORD" "JWT_SECRET" "R2_ENDPOINT_URL"
        "R2_ACCESS_KEY_ID" "R2_SECRET_ACCESS_KEY" "R2_BUCKET_NAME"
        "STRIPE_SECRET_KEY" "STRIPE_WEBHOOK_SECRET"
    )

    local missing=()
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=<\|^${var}=$" "$ENV_FILE" 2>/dev/null || ! grep -q "^${var}=" "$ENV_FILE" 2>/dev/null; then
            missing+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing or placeholder values for: ${missing[*]}"
        log_info "Edit .env.prod and set real values before deploying."
        exit 1
    fi
}

deploy() {
    log_info "Checking environment..."
    check_env

    log_info "Building images..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --pull

    log_info "Running database migrations..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm backend \
        alembic upgrade head

    log_info "Starting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

    log_info "Waiting for services to be healthy..."
    sleep 15

    log_info "Checking health..."
    local health
    health=$(curl -sf http://localhost/health/ready 2>/dev/null || echo "unreachable")
    if echo "$health" | grep -q '"status": "healthy"'; then
        log_info "All services healthy!"
    else
        log_warn "Health check not yet passing. Check logs: ./scripts/deploy.sh logs"
    fi

    log_info "Deploy complete!"
    log_info "  Frontend: http://localhost"
    log_info "  API:      http://localhost/api"
    log_info "  Health:   http://localhost/health/ready"
    log_info "  Flower:   http://localhost:5555 (if exposed)"
}

stop() {
    log_info "Stopping all services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    log_info "All services stopped."
}

logs() {
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f --tail=100 "${1:-}"
}

restart() {
    log_info "Restarting services..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart
    log_info "Services restarted."
}

status() {
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
}

migrate() {
    log_info "Running database migrations..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm backend \
        alembic upgrade head
    log_info "Migrations complete."
}

case "${1:-deploy}" in
    deploy)   deploy ;;
    stop)     stop ;;
    logs)     logs "${2:-}" ;;
    restart)  restart ;;
    status)   status ;;
    migrate)  migrate ;;
    *)
        echo "Usage: $0 {deploy|stop|logs|restart|status|migrate}"
        echo ""
        echo "Commands:"
        echo "  deploy    Build and start all services (default)"
        echo "  stop      Stop and remove all containers"
        echo "  logs      Follow logs (optionally for a specific service)"
        echo "  restart   Restart all services"
        echo "  status    Show container status"
        echo "  migrate   Run database migrations only"
        exit 1
        ;;
esac
