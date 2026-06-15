from uuid import uuid4

import pytest
from httpx import AsyncClient


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
