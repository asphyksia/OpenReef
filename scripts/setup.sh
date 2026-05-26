#!/bin/bash
# Setup: start infra + run migrations
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

"$SCRIPT_DIR/infra.sh"
"$SCRIPT_DIR/migrate.sh"

echo ""
echo "=> Setup completo. Lista para start-all.sh"
