"""Shared test fixtures for OpenReef backend tests."""
import os
import uuid
import asyncio
import subprocess
import sys
from typing import AsyncGenerator
from unittest.mock import MagicMock

# Disable rate limiting BEFORE any app imports
from slowapi import Limiter
_noop_limit = lambda *args, **kwargs: lambda f: f
Limiter.limit = _noop_limit

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import get_db
from app.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5444/openreef_test",
)

TEST_TABLES = ["credit_ledger", "processed_events", "jobs", "datasets", "providers", "base_models", "users"]


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    db_name = "openreef_test"
    try:
        result = subprocess.run(
            ["psql", "-h", "127.0.0.1", "-p", "5444", "-U", "postgres",
             "-t", "-c", f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"],
            capture_output=True, text=True, check=False,
        )
        if "1" not in result.stdout:
            subprocess.run(
                ["psql", "-h", "127.0.0.1", "-p", "5444", "-U", "postgres", "-c", f"CREATE DATABASE {db_name}"],
                capture_output=True, check=False,
            )
    except FileNotFoundError:
        pass
    yield


@pytest_asyncio.fixture
async def engine(setup_test_database):
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create partial unique index (not in metadata, only in migration)
        await conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_one_active_job_per_user ON jobs (user_id)
            WHERE status IN ('pending', 'queued', 'provisioning', 'running', 'checkpointing')
        """))
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Single session per test with truncate-based cleanup."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # Truncate tables before test (in same session, committed before yield)
        for table in TEST_TABLES:
            try:
                await session.execute(text(f"TRUNCATE {table} CASCADE"))
            except Exception:
                pass
        await session.commit()
        yield session
        await session.close()


@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(db) -> AsyncGenerator:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=True)

    class AuthClient:
        def __init__(self):
            self.client = AsyncClient(transport=transport, base_url="http://test")
            self.csrf_token = None
            self.user_info = None

        async def register(self, email=None, password="testpassword123"):
            email = email or f"test_{uuid.uuid4().hex[:8]}@test.com"
            return await self.client.post("/api/auth/register", json={"email": email, "password": password})

        async def login(self, email, password):
            resp = await self.client.post("/api/auth/login", json={"email": email, "password": password})
            if resp.status_code == 200:
                self.csrf_token = resp.cookies.get("csrf_token")
                me = await self.get("/api/auth/me")
                if me.status_code == 200:
                    self.user_info = me.json()
            return resp

        async def register_and_login(self, email=None, password="testpassword123"):
            email = email or f"test_{uuid.uuid4().hex[:8]}@test.com"
            await self.register(email, password)
            return await self.login(email, password)

        def _csrf_headers(self, kwargs):
            headers = kwargs.pop("headers", {}) or {}
            if self.csrf_token:
                headers["X-CSRF-Token"] = self.csrf_token
            kwargs["headers"] = headers
            return kwargs

        async def post(self, url, *args, **kwargs):
            return await self.client.post(url, *args, **self._csrf_headers(kwargs))

        async def put(self, url, *args, **kwargs):
            return await self.client.put(url, *args, **self._csrf_headers(kwargs))

        async def delete(self, url, *args, **kwargs):
            return await self.client.delete(url, *args, **self._csrf_headers(kwargs))

        async def patch(self, url, *args, **kwargs):
            return await self.client.patch(url, *args, **self._csrf_headers(kwargs))

        async def get(self, url, *args, **kwargs):
            return await self.client.get(url, *args, **kwargs)

        async def add_credits(self, amount):
            return await self.post("/api/payments/dev-add-credits", json={"amount": amount})

        async def close(self):
            await self.client.aclose()

    ac = AuthClient()
    yield ac
    await ac.close()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_base_model(db):
    from app.models.base_model import BaseModel as DBBaseModel
    model = DBBaseModel(
        name="test-model/Llama-3.2-3B", param_count=3, min_vram_gb=8,
        is_active=True, supported_adapters=["lora", "qlora"],
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@pytest_asyncio.fixture
async def user_with_dataset(auth_client, db, seed_base_model):
    await auth_client.register_and_login()
    await auth_client.add_credits(100)

    from app.models.dataset import Dataset
    dataset = Dataset(
        user_id=uuid.UUID(auth_client.user_info["id"]),
        name="test-dataset", filename="test.jsonl", format="jsonl",
        size_bytes=1024, row_count=100, token_count=5000,
        validation_status="valid", validation_errors=[],
        r2_key="datasets/test/test.jsonl",
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    return {"auth": auth_client, "user": auth_client.user_info, "base_model": seed_base_model, "dataset": dataset}
