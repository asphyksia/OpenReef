"""Tests for jobs API endpoints."""
import uuid

import pytest


class TestCreateJob:
    async def test_create_job_success(self, auth_client, db, seed_base_model):
        await auth_client.register_and_login()
        user_id = uuid.UUID(auth_client.user_info["id"])

        await auth_client.add_credits(50)

        from app.models.dataset import Dataset
        dataset = Dataset(
            user_id=user_id, name="ds", filename="test.jsonl", format="jsonl",
            size_bytes=1024, row_count=100, token_count=5000,
            validation_status="valid", validation_errors=[],
            r2_key="datasets/test/test.jsonl",
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)

        resp = await auth_client.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(seed_base_model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["preset"] == "fast"
        assert data["adapter"] == "lora"

    async def test_create_job_duplicate_active_blocked(self, auth_client, db, seed_base_model):
        """Test that the DB unique index prevents two active jobs for the same user."""
        await auth_client.register_and_login()
        user_id = uuid.UUID(auth_client.user_info["id"])

        await auth_client.add_credits(100)

        from app.models.dataset import Dataset
        from app.models.job import Job

        # Create first dataset
        dataset1 = Dataset(
            user_id=user_id, name="ds1", filename="test1.jsonl", format="jsonl",
            size_bytes=1024, row_count=100, token_count=5000,
            validation_status="valid", validation_errors=[],
            r2_key="datasets/test/test1.jsonl",
        )
        db.add(dataset1)

        # Create second dataset
        dataset2 = Dataset(
            user_id=user_id, name="ds2", filename="test2.jsonl", format="jsonl",
            size_bytes=1024, row_count=100, token_count=5000,
            validation_status="valid", validation_errors=[],
            r2_key="datasets/test/test2.jsonl",
        )
        db.add(dataset2)
        await db.commit()
        await db.refresh(dataset1)
        await db.refresh(dataset2)

        # Create first job directly in DB (bypass service check)
        job1 = Job(
            user_id=user_id, dataset_id=dataset1.id,
            base_model_id=seed_base_model.id, preset="fast", adapter="lora",
            status="pending", estimated_cost=1.0,
        )
        db.add(job1)
        await db.commit()

        # Try to create second active job — should fail at DB level
        job2 = Job(
            user_id=user_id, dataset_id=dataset2.id,
            base_model_id=seed_base_model.id, preset="fast", adapter="lora",
            status="pending", estimated_cost=1.0,
        )
        db.add(job2)
        with pytest.raises(Exception):  # IntegrityError from unique index
            await db.commit()

    async def test_create_job_insufficient_balance(self, auth_client, db, seed_base_model):
        await auth_client.register_and_login()
        user_id = uuid.UUID(auth_client.user_info["id"])

        from app.models.dataset import Dataset
        dataset = Dataset(
            user_id=user_id, name="ds", filename="test.jsonl", format="jsonl",
            size_bytes=1024, row_count=100, token_count=5000,
            validation_status="valid", validation_errors=[],
            r2_key="datasets/test/test.jsonl",
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)

        resp = await auth_client.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(seed_base_model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        assert resp.status_code == 402

    async def test_create_job_invalid_model(self, auth_client, db):
        await auth_client.register_and_login()
        user_id = uuid.UUID(auth_client.user_info["id"])

        await auth_client.add_credits(50)

        from app.models.dataset import Dataset
        dataset = Dataset(
            user_id=user_id, name="ds", filename="test.jsonl", format="jsonl",
            size_bytes=1024, row_count=100, token_count=5000,
            validation_status="valid", validation_errors=[],
            r2_key="datasets/test/test.jsonl",
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)

        resp = await auth_client.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(uuid.uuid4()),
            "preset": "fast",
            "adapter": "lora",
        })
        assert resp.status_code == 400

    async def test_create_job_invalid_adapter(self, auth_client, db, seed_base_model):
        await auth_client.register_and_login()
        user_id = uuid.UUID(auth_client.user_info["id"])

        await auth_client.add_credits(50)

        from app.models.dataset import Dataset
        dataset = Dataset(
            user_id=user_id, name="ds", filename="test.jsonl", format="jsonl",
            size_bytes=1024, row_count=100, token_count=5000,
            validation_status="valid", validation_errors=[],
            r2_key="datasets/test/test.jsonl",
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)

        resp = await auth_client.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(seed_base_model.id),
            "preset": "fast",
            "adapter": "invalid",
        })
        assert resp.status_code == 400

    async def test_create_job_unauthenticated(self, client, seed_base_model):
        resp = await client.post("/api/jobs", json={
            "dataset_id": str(uuid.uuid4()),
            "base_model_id": str(seed_base_model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        assert resp.status_code == 401


class TestConfirmJob:
    async def test_confirm_job_success(self, user_with_dataset):
        auth = user_with_dataset["auth"]
        dataset = user_with_dataset["dataset"]
        model = user_with_dataset["base_model"]

        resp = await auth.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        resp = await auth.post(f"/api/jobs/{job_id}/confirm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"

    async def test_confirm_job_idempotent(self, user_with_dataset):
        auth = user_with_dataset["auth"]
        dataset = user_with_dataset["dataset"]
        model = user_with_dataset["base_model"]

        resp = await auth.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        job_id = resp.json()["id"]

        resp1 = await auth.post(f"/api/jobs/{job_id}/confirm")
        assert resp1.status_code == 200

        resp2 = await auth.post(f"/api/jobs/{job_id}/confirm")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "queued"

    async def test_confirm_job_not_found(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.post(f"/api/jobs/{uuid.uuid4()}/confirm")
        assert resp.status_code == 404

    async def test_confirm_job_wrong_user(self, auth_client, db, seed_base_model):
        await auth_client.register_and_login()
        user_a_id = uuid.UUID(auth_client.user_info["id"])
        await auth_client.add_credits(50)

        from app.models.dataset import Dataset
        dataset = Dataset(
            user_id=user_a_id, name="ds", filename="test.jsonl", format="jsonl",
            size_bytes=1024, row_count=100, token_count=5000,
            validation_status="valid", validation_errors=[],
            r2_key="datasets/test/test.jsonl",
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)

        resp = await auth_client.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(seed_base_model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        job_id = resp.json()["id"]

        # User B tries to confirm
        await auth_client.register_and_login()
        resp = await auth_client.post(f"/api/jobs/{job_id}/confirm")
        assert resp.status_code == 403


class TestCancelJob:
    async def test_cancel_pending_full_refund(self, user_with_dataset):
        auth = user_with_dataset["auth"]
        dataset = user_with_dataset["dataset"]
        model = user_with_dataset["base_model"]

        resp = await auth.get("/api/payments/balance")
        initial_balance = resp.json()["balance"]

        # Create job but DON'T confirm (stays in pending)
        resp = await auth.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        job_id = resp.json()["id"]

        # Cancel while pending → 100% refund (no charge was made)
        resp = await auth.post(f"/api/jobs/{job_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

        # Balance should be at least unchanged (no charge was made, or refund applied)
        resp = await auth.get("/api/payments/balance")
        final_balance = resp.json()["balance"]
        assert final_balance >= initial_balance

    async def test_cancel_queued_partial_refund(self, user_with_dataset):
        auth = user_with_dataset["auth"]
        dataset = user_with_dataset["dataset"]
        model = user_with_dataset["base_model"]

        resp = await auth.get("/api/payments/balance")
        initial_balance = resp.json()["balance"]

        resp = await auth.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        job_id = resp.json()["id"]
        await auth.post(f"/api/jobs/{job_id}/confirm")

        resp = await auth.get("/api/payments/balance")
        after_charge = resp.json()["balance"]
        assert after_charge < initial_balance

        resp = await auth.post(f"/api/jobs/{job_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

        # Should have 50% refund
        resp = await auth.get("/api/payments/balance")
        final_balance = resp.json()["balance"]
        assert final_balance > after_charge

    async def test_cancel_twice(self, user_with_dataset):
        auth = user_with_dataset["auth"]
        dataset = user_with_dataset["dataset"]
        model = user_with_dataset["base_model"]

        resp = await auth.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(model.id),
            "preset": "fast",
            "adapter": "lora",
        })
        job_id = resp.json()["id"]

        resp = await auth.post(f"/api/jobs/{job_id}/cancel")
        assert resp.status_code == 200

        resp = await auth.post(f"/api/jobs/{job_id}/cancel")
        assert resp.status_code == 400


class TestListJobs:
    async def test_list_jobs_empty(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_jobs_with_jobs(self, user_with_dataset):
        auth = user_with_dataset["auth"]
        dataset = user_with_dataset["dataset"]
        model = user_with_dataset["base_model"]

        await auth.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(model.id),
            "preset": "fast",
            "adapter": "lora",
        })

        resp = await auth.get("/api/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 1
        assert jobs[0]["preset"] == "fast"

    async def test_list_jobs_unauthenticated(self, client):
        resp = await client.get("/api/jobs")
        assert resp.status_code == 401


class TestGetJob:
    async def test_get_job_success(self, user_with_dataset):
        auth = user_with_dataset["auth"]
        dataset = user_with_dataset["dataset"]
        model = user_with_dataset["base_model"]

        resp = await auth.post("/api/jobs", json={
            "dataset_id": str(dataset.id),
            "base_model_id": str(model.id),
            "preset": "balanced",
            "adapter": "lora",
        })
        job_id = resp.json()["id"]

        resp = await auth.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == job_id
        assert data["preset"] == "balanced"

    async def test_get_job_not_found(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.get(f"/api/jobs/{uuid.uuid4()}")
        assert resp.status_code == 404
