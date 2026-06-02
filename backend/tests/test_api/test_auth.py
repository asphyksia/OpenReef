"""Tests for auth API endpoints."""
import uuid


class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "newuser@test.com", "password": "securepassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "registered"
        assert data["verification_required"] is False

    async def test_register_duplicate_email(self, client):
        email = "dup@test.com"
        await client.post("/api/auth/register", json={"email": email, "password": "securepassword123"})
        resp = await client.post("/api/auth/register", json={"email": email, "password": "anotherpassword"})
        assert resp.status_code == 409

    async def test_register_short_password(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "short@test.com", "password": "123"},
        )
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "securepassword123"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client):
        email = "loginuser@test.com"
        password = "securepassword123"
        await client.post("/api/auth/register", json={"email": email, "password": password})

        resp = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200
        assert "token" in resp.cookies
        assert "csrf_token" in resp.cookies

    async def test_login_wrong_password(self, client):
        email = "wrongpass@test.com"
        await client.post("/api/auth/register", json={"email": email, "password": "correctpassword"})

        resp = await client.post("/api/auth/login", json={"email": email, "password": "wrongpassword"})
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nobody@test.com", "password": "anypassword"},
        )
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_success(self, auth_client):
        await auth_client.register_and_login()

        resp = await auth_client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["message"] == "logged out"

    async def test_logout_unauthenticated(self, client):
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 401


class TestMe:
    async def test_me_success(self, auth_client):
        await auth_client.register_and_login()

        resp = await auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "email" in data
        assert "balance" in data
        assert data["balance"] == 0.0

    async def test_me_unauthenticated(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_after_logout(self, auth_client):
        await auth_client.register_and_login()
        await auth_client.post("/api/auth/logout")

        resp = await auth_client.get("/api/auth/me")
        assert resp.status_code == 401
