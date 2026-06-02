"""Tests for credit_service module."""
import uuid

import pytest
from fastapi import HTTPException

from app.services import credit_service
from app.models.user import User


async def _create_user(db):
    """Helper to create and persist a test user."""
    user = User(email=f"test_{uuid.uuid4().hex[:8]}@test.com", password_hash="hash")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestGetBalance:
    async def test_balance_zero_new_user(self, db):
        user_id = uuid.uuid4()
        balance = await credit_service.get_balance(db, user_id)
        assert balance == 0.0

    async def test_balance_after_credits(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 50, "test")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 50.0

    async def test_balance_after_charge(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()
        await credit_service.charge_credits(db, user.id, 30, None, "job")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 70.0

    async def test_balance_after_refund(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()
        await credit_service.charge_credits(db, user.id, 50, None, "job")
        await db.commit()
        await credit_service.refund_credits(db, user.id, 25, None, "partial refund")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 75.0


class TestAddCredits:
    async def test_add_credits(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 75, "purchase")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 75.0

    async def test_add_credits_multiple(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 25, "first")
        await db.commit()
        await credit_service.add_credits(db, user.id, 30, "second")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 55.0


class TestChargeCredits:
    async def test_charge_success(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()
        await credit_service.charge_credits(db, user.id, 40, None, "job charge")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 60.0

    async def test_charge_insufficient_balance(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 10, "test")
        await db.commit()
        with pytest.raises(HTTPException) as exc_info:
            await credit_service.charge_credits(db, user.id, 50, None, "job charge")
        assert exc_info.value.status_code == 402

    async def test_charge_exact_balance(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 50, "test")
        await db.commit()
        await credit_service.charge_credits(db, user.id, 50, None, "job charge")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 0.0


class TestRefundCredits:
    async def test_refund_full(self, db):
        user = await _create_user(db)
        job_id = uuid.uuid4()
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()
        await credit_service.charge_credits(db, user.id, 100, None, "job")
        await db.commit()
        await credit_service.refund_credits(db, user.id, 100, None, "full refund")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 100.0

    async def test_refund_partial(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()
        await credit_service.charge_credits(db, user.id, 50, None, "job")
        await db.commit()
        await credit_service.refund_credits(db, user.id, 25, None, "50% refund")
        await db.commit()
        balance = await credit_service.get_balance(db, user.id)
        assert balance == 75.0

    async def test_refund_idempotent(self, db):
        """Double refund should only apply once."""
        user = await _create_user(db)
        job_id = uuid.uuid4()
        await credit_service.add_credits(db, user.id, 100, "test")
        await db.commit()
        await credit_service.charge_credits(db, user.id, 50, None, "job")
        await db.commit()

        # First refund
        await credit_service.refund_credits(db, user.id, 25, None, "refund")
        await db.commit()
        balance_after_first = await credit_service.get_balance(db, user.id)

        # Second refund for same job should be skipped
        await credit_service.refund_credits(db, user.id, 25, None, "refund again")
        await db.commit()
        balance_after_second = await credit_service.get_balance(db, user.id)

        assert balance_after_first == balance_after_second


class TestGetBalanceForUpdate:
    async def test_lock_and_read(self, db):
        user = await _create_user(db)
        await credit_service.add_credits(db, user.id, 42, "test")
        await db.commit()
        balance = await credit_service.get_balance_for_update(db, user.id)
        assert balance == 42.0
