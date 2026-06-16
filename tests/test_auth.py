from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security import create_oauth_state_token
from app.services.google_oauth import GoogleUserInfo


def unique_email() -> str:
    return f"test_{uuid4().hex[:8]}@example.com"


async def test_health(test_client: AsyncClient):
    response = await test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_register_success(test_client: AsyncClient):
    response = await test_client.post(
        "/auth/register",
        json={"email": unique_email(), "password": "strongpass1"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "email" in data


async def test_register_duplicate_email(test_client: AsyncClient):
    email = unique_email()
    payload = {"email": email, "password": "strongpass1"}
    await test_client.post("/auth/register", json=payload)
    response = await test_client.post("/auth/register", json=payload)
    assert response.status_code == 409


async def test_login_success(test_client: AsyncClient):
    email = unique_email()
    password = "strongpass1"
    await test_client.post("/auth/register", json={"email": email, "password": password})
    response = await test_client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(test_client: AsyncClient):
    email = unique_email()
    await test_client.post("/auth/register", json={"email": email, "password": "strongpass1"})
    response = await test_client.post(
        "/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert response.status_code == 401


async def test_google_login_redirects_to_google(test_client: AsyncClient):
    response = await test_client.get("/auth/google/login")
    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]


async def test_google_callback_creates_new_user(test_client: AsyncClient):
    email = unique_email()
    state = create_oauth_state_token()
    with patch(
        "app.routers.auth.exchange_code_for_userinfo", new_callable=AsyncMock
    ) as mock_exchange:
        mock_exchange.return_value = GoogleUserInfo(
            sub="google-sub-123", email=email, email_verified=True, name="Test User"
        )
        response = await test_client.get(
            "/auth/google/callback", params={"code": "fake-code", "state": state}
        )
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith("http")
    assert "token=" in location

    token = location.split("token=")[1]
    me = await test_client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


async def test_google_callback_links_existing_email_user(test_client: AsyncClient):
    email = unique_email()
    await test_client.post("/auth/register", json={"email": email, "password": "strongpass1"})

    state = create_oauth_state_token()
    with patch(
        "app.routers.auth.exchange_code_for_userinfo", new_callable=AsyncMock
    ) as mock_exchange:
        mock_exchange.return_value = GoogleUserInfo(
            sub="google-sub-456", email=email, email_verified=True, name="Test User"
        )
        response = await test_client.get(
            "/auth/google/callback", params={"code": "fake-code", "state": state}
        )
    assert response.status_code in (302, 307)
    token = response.headers["location"].split("token=")[1]

    me = await test_client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200

    register_again = await test_client.post(
        "/auth/register", json={"email": email, "password": "anotherpass1"}
    )
    assert register_again.status_code == 409


async def test_google_callback_invalid_state(test_client: AsyncClient):
    response = await test_client.get(
        "/auth/google/callback", params={"code": "fake-code", "state": "not-a-real-token"}
    )
    assert response.status_code == 400


async def test_google_callback_google_error(test_client: AsyncClient):
    response = await test_client.get(
        "/auth/google/callback", params={"error": "access_denied"}
    )
    assert response.status_code in (302, 307)
    assert "error=access_denied" in response.headers["location"]
