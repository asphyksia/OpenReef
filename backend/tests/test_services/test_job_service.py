"""Tests for job_service module."""
import uuid

import pytest
from fastapi import HTTPException

from app.services import job_service
from app.services.pricing import PRESET_HOURS
from app.models.user import User
from app.models.dataset import Dataset
from app.models.job import Job


async def _create_user(db, email=None):
    email = email or f"test_{uuid.uuid4().hex[:8]}@test.com"
    user = User(email=email, password_hash="hash")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_dataset(db, user_id):
    dataset = Dataset(
        user_id=user_id, name="ds", filename="test.jsonl", format="jsonl",
        size_bytes=1024, row_count=100, token_count=5000,
        validation_status="valid", validation_errors=[],
        r2_key="datasets/test/test.jsonl",
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


class TestEstimateCost:
    async def test_cost_3b_fast(self, db, seed_base_model):
        cost = await job_service.estimate_cost(db, seed_base_model.id, "fast")
        assert cost > 0
        assert isinstance(cost, float)

    async def test_cost_3b_quality(self, db, seed_base_model):
        cost_fast = await job_service.estimate_cost(db, seed_base_model.id, "fast")
        cost_quality = await job_service.estimate_cost(db, seed_base_model.id, "quality")
        assert cost_quality > cost_fast

    async def test_cost_with_token_count(self, db, seed_base_model):
        cost_no_tokens = await job_service.estimate_cost(db, seed_base_model.id, "fast", token_count=0)
        cost_with_tokens = await job_service.estimate_cost(db, seed_base_model.id, "fast", token_count=50000)
        assert cost_with_tokens <= cost_no_tokens

    async def test_cost_invalid_model(self, db):
        with pytest.raises(HTTPException) as exc_info:
            await job_service.estimate_cost(db, uuid.uuid4(), "fast")
        assert exc_info.value.status_code == 400

    async def test_cost_invalid_preset(self, db, seed_base_model):
        with pytest.raises(HTTPException) as exc_info:
            await job_service.estimate_cost(db, seed_base_model.id, "nonexistent")
        assert exc_info.value.status_code == 400


class TestHasActiveJob:
    async def test_no_active_job(self, db):
        user_id = uuid.uuid4()
        result = await job_service.has_active_job(db, user_id)
        assert result is False

    async def test_has_pending_job(self, db, seed_base_model):
        user = await _create_user(db, "active@test.com")
        dataset = await _create_dataset(db, user.id)

        job = Job(
            user_id=user.id, dataset_id=dataset.id,
            base_model_id=seed_base_model.id, preset="fast", adapter="lora",
            status="pending",
        )
        db.add(job)
        await db.commit()

        result = await job_service.has_active_job(db, user.id)
        assert result is True

    async def test_completed_job_not_active(self, db, seed_base_model):
        user = await _create_user(db, "completed@test.com")
        dataset = await _create_dataset(db, user.id)

        job = Job(
            user_id=user.id, dataset_id=dataset.id,
            base_model_id=seed_base_model.id, preset="fast", adapter="lora",
            status="completed",
        )
        db.add(job)
        await db.commit()

        result = await job_service.has_active_job(db, user.id)
        assert result is False

    async def test_failed_job_not_active(self, db, seed_base_model):
        user = await _create_user(db, "failed@test.com")
        dataset = await _create_dataset(db, user.id)

        job = Job(
            user_id=user.id, dataset_id=dataset.id,
            base_model_id=seed_base_model.id, preset="fast", adapter="lora",
            status="failed",
        )
        db.add(job)
        await db.commit()

        result = await job_service.has_active_job(db, user.id)
        assert result is False


class TestCreateJob:
    async def test_create_job_success(self, db, seed_base_model):
        from app.services import credit_service

        user = await _create_user(db, "createjob@test.com")
        dataset = await _create_dataset(db, user.id)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()

        job = await job_service.create_job(
            db, user.id, dataset.id, seed_base_model.id, "fast", "lora"
        )
        assert job.status == "pending"
        assert job.user_id == user.id
        assert job.dataset_id == dataset.id
        assert job.estimated_cost is not None
        assert job.estimated_cost > 0

    async def test_create_job_insufficient_balance(self, db, seed_base_model):
        user = await _create_user(db, "nobalance@test.com")
        dataset = await _create_dataset(db, user.id)

        with pytest.raises(HTTPException) as exc_info:
            await job_service.create_job(
                db, user.id, dataset.id, seed_base_model.id, "fast", "lora"
            )
        assert exc_info.value.status_code == 402

    async def test_create_job_duplicate(self, db, seed_base_model):
        from app.services import credit_service

        user = await _create_user(db, "duplicate@test.com")
        dataset = await _create_dataset(db, user.id)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()

        await job_service.create_job(
            db, user.id, dataset.id, seed_base_model.id, "fast", "lora"
        )

        with pytest.raises(HTTPException) as exc_info:
            await job_service.create_job(
                db, user.id, dataset.id, seed_base_model.id, "fast", "lora"
            )
        assert exc_info.value.status_code == 400


class TestConfirmJob:
    async def test_confirm_job_charges_credits(self, db, seed_base_model):
        from app.services import credit_service

        user = await _create_user(db, "confirm@test.com")
        dataset = await _create_dataset(db, user.id)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()

        job = await job_service.create_job(
            db, user.id, dataset.id, seed_base_model.id, "fast", "lora"
        )
        initial_balance = await credit_service.get_balance(db, user.id)

        confirmed = await job_service.confirm_job(db, user.id, job.id)
        assert confirmed.status == "queued"

        final_balance = await credit_service.get_balance(db, user.id)
        assert final_balance < initial_balance

    async def test_confirm_job_idempotent(self, db, seed_base_model):
        from app.services import credit_service

        user = await _create_user(db, "idempotent@test.com")
        dataset = await _create_dataset(db, user.id)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()

        job = await job_service.create_job(
            db, user.id, dataset.id, seed_base_model.id, "fast", "lora"
        )

        await job_service.confirm_job(db, user.id, job.id)
        balance_after_first = await credit_service.get_balance(db, user.id)

        await job_service.confirm_job(db, user.id, job.id)
        balance_after_second = await credit_service.get_balance(db, user.id)

        assert balance_after_first == balance_after_second

    async def test_confirm_wrong_user(self, db, seed_base_model):
        from app.services import credit_service

        user_a = await _create_user(db, "usera@test.com")
        user_b = await _create_user(db, "userb@test.com")
        dataset = await _create_dataset(db, user_a.id)
        await credit_service.add_credits(db, user_a.id, 100, "test")
        await db.commit()

        job = await job_service.create_job(
            db, user_a.id, dataset.id, seed_base_model.id, "fast", "lora"
        )

        with pytest.raises(HTTPException) as exc_info:
            await job_service.confirm_job(db, user_b.id, job.id)
        assert exc_info.value.status_code == 403
