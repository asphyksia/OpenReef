#!/bin/bash
# Start infrastructure: postgres, redis, minio
set -e

cd "$(dirname "$0")/.."

echo "=> Starting docker infra (postgres, redis, minio)..."
docker compose up -d postgres redis minio

echo "=> Waiting for postgres..."
until docker exec openreef-postgres-1 pg_isready -U postgres 2>/dev/null; do
  sleep 1
done

echo "=> Waiting for redis..."
until docker exec openreef-redis-1 redis-cli ping 2>/dev/null | grep -q PONG; do
  sleep 1
done

echo "=> Creating MinIO bucket..."
docker exec openreef-minio-1 mc mb local/openreef-mvp 2>/dev/null || true

echo "=> Infra ready."
echo "   PostgreSQL : 127.0.0.1:5444"
echo "   Redis      : 127.0.0.1:6379"
echo "   MinIO API   : 127.0.0.1:9000"
echo "   MinIO UI    : 127.0.0.1:9001"
