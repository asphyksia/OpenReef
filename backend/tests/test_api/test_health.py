"""Tests for health endpoints."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import status
from httpx import AsyncClient

from app.config import settings


class TestHealthBasic:
    """GET /health — no dependencies."""

    async def test_health_returns_200(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestHealthReady:
    """GET /health/ready — checks all infrastructure dependencies."""

    @patch("app.api.health._check_database")
    @patch("app.api.health._check_redis")
    @patch("app.api.health._check_storage")
    async def test_healthy_returns_200_without_metrics(
        self, mock_storage, mock_redis, mock_db, client: AsyncClient
    ):
        mock_db.return_value = (True, "connected")
        mock_redis.return_value = (True, "connected")
        mock_storage.return_value = (True, "connected")

        resp = await client.get("/health/ready")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "connected"
        assert data["redis"]["status"] == "connected"
        assert data["storage"]["status"] == "connected"
        assert "metrics" not in data

    @patch("app.api.health._check_database")
    @patch("app.api.health._check_redis")
    @patch("app.api.health._check_storage")
    async def test_database_down_returns_503(
        self, mock_storage, mock_redis, mock_db, client: AsyncClient
    ):
        mock_db.return_value = (False, "connection refused")
        mock_redis.return_value = (True, "connected")
        mock_storage.return_value = (True, "connected")

        resp = await client.get("/health/ready")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["database"]["status"] == "error"
        assert "metrics" not in data

    @patch("app.api.health._check_database")
    @patch("app.api.health._check_redis")
    @patch("app.api.health._check_storage")
    async def test_redis_down_returns_503(
        self, mock_storage, mock_redis, mock_db, client: AsyncClient
    ):
        mock_db.return_value = (True, "connected")
        mock_redis.return_value = (False, "connection refused")
        mock_storage.return_value = (True, "connected")

        resp = await client.get("/health/ready")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["redis"]["status"] == "error"
        assert "metrics" not in data

    @patch("app.api.health._check_database")
    @patch("app.api.health._check_redis")
    @patch("app.api.health._check_storage")
    async def test_storage_down_returns_503(
        self, mock_storage, mock_redis, mock_db, client: AsyncClient
    ):
        mock_db.return_value = (True, "connected")
        mock_redis.return_value = (True, "connected")
        mock_storage.return_value = (False, "bucket not found")

        resp = await client.get("/health/ready")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["storage"]["status"] == "error"
        assert "metrics" not in data

    @patch("app.api.health._check_database")
    @patch("app.api.health._check_redis")
    @patch("app.api.health._check_storage")
    async def test_all_down_returns_503(
        self, mock_storage, mock_redis, mock_db, client: AsyncClient
    ):
        mock_db.return_value = (False, "connection refused")
        mock_redis.return_value = (False, "connection refused")
        mock_storage.return_value = (False, "bucket not found")

        resp = await client.get("/health/ready")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["database"]["status"] == "error"
        assert data["redis"]["status"] == "error"
        assert data["storage"]["status"] == "error"
        assert "metrics" not in data

    @patch("app.api.health._check_database")
    @patch("app.api.health._check_redis")
    @patch("app.api.health._check_storage")
    async def test_no_business_metrics_in_response(
        self, mock_storage, mock_redis, mock_db, client: AsyncClient
    ):
        """Verify /health/ready does not expose business metrics (total_users, active_jobs, etc.)."""
        mock_db.return_value = (True, "connected")
        mock_redis.return_value = (True, "connected")
        mock_storage.return_value = (True, "connected")

        resp = await client.get("/health/ready")

        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" not in data
        assert "active_jobs" not in data
        assert "active_providers" not in data
        assert "jobs_last_24h" not in data
        assert "metrics" not in data


class TestAdminMetrics:
    """GET /admin/metrics — protected by admin API key."""

    async def test_metrics_without_key_returns_403(self, client: AsyncClient):
        resp = await client.get("/admin/metrics")
        assert resp.status_code == 403

    async def test_metrics_with_wrong_key_returns_403(self, client: AsyncClient):
        resp = await client.get("/admin/metrics", headers={"Authorization": "Bearer wrong-key"})
        assert resp.status_code == 403

    @patch("app.config.settings.admin_api_key", "test-admin-key-123")
    async def test_metrics_with_correct_key_returns_200(self, client: AsyncClient):
        resp = await client.get(
            "/admin/metrics",
            headers={"Authorization": "Bearer test-admin-key-123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "metrics" in data
        assert "active_jobs" in data["metrics"]
        assert "total_users" in data["metrics"]
        assert "active_providers" in data["metrics"]
        assert "jobs_last_24h" in data["metrics"]

    @patch("app.config.settings.admin_api_key", "")
    async def test_metrics_with_empty_admin_key_returns_403(self, client: AsyncClient):
        """When admin_api_key is not configured, all requests should be denied."""
        resp = await client.get(
            "/admin/metrics",
            headers={"Authorization": "Bearer any-key"},
        )
        assert resp.status_code == 403

    async def test_metrics_requires_bearer_scheme(self, client: AsyncClient):
        """Non-Bearer authorization should be rejected."""
        resp = await client.get(
            "/admin/metrics",
            headers={"Authorization": "Basic some-key"},
        )
        assert resp.status_code == 403

    async def test_metrics_not_in_health_ready(self, client: AsyncClient):
        """Business metrics should not leak through /health/ready."""
        from unittest.mock import patch

        with patch("app.api.health._check_database", return_value=(True, "connected")), \
             patch("app.api.health._check_redis", return_value=(True, "connected")), \
             patch("app.api.health._check_storage", return_value=(True, "connected")):

            resp = await client.get("/health/ready")
            data = resp.json()

            assert "total_users" not in data
            assert "active_jobs" not in data
            assert data.get("metrics") is None or "total_users" not in data.get("metrics", {})
