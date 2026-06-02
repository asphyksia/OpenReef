"""Tests for payments API endpoints."""


class TestBalance:
    async def test_balance_zero(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.get("/api/payments/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 0.0
        assert data["currency"] == "USD"

    async def test_balance_unauthenticated(self, client):
        resp = await client.get("/api/payments/balance")
        assert resp.status_code == 401


class TestDevAddCredits:
    async def test_add_credits_success(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.add_credits(50)
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 50.0

    async def test_add_credits_multiple_times(self, auth_client):
        await auth_client.register_and_login()
        await auth_client.add_credits(25)
        resp = await auth_client.add_credits(30)
        assert resp.status_code == 200
        data = resp.json()
        assert data["balance"] == 55.0

    async def test_add_credits_invalid_amount(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.post("/api/payments/dev-add-credits", json={"amount": -10})
        assert resp.status_code == 422

    async def test_add_credits_zero(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.post("/api/payments/dev-add-credits", json={"amount": 0})
        assert resp.status_code == 422

    async def test_add_credits_unauthenticated(self, client):
        resp = await client.post("/api/payments/dev-add-credits", json={"amount": 50})
        assert resp.status_code == 401


class TestCheckoutSession:
    async def test_checkout_disabled_in_dev_mode(self, auth_client):
        await auth_client.register_and_login()
        resp = await auth_client.post("/api/payments/checkout-session", json={"amount_usd": 10})
        assert resp.status_code == 409
