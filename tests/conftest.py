from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
async def test_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_headers(test_client: AsyncClient) -> dict:
    email = f"test_{uuid4().hex[:8]}@example.com"
    await test_client.post("/auth/register", json={"email": email, "password": "strongpass1"})
    resp = await test_client.post("/auth/login", json={"email": email, "password": "strongpass1"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def project_id(test_client: AsyncClient, auth_headers: dict) -> str:
    resp = await test_client.post(
        "/projects", json={"name": "Test Project"}, headers=auth_headers
    )
    return resp.json()["id"]
