from uuid import uuid4

import pytest
from httpx import AsyncClient


async def test_create_project(test_client: AsyncClient, auth_headers: dict):
    response = await test_client.post(
        "/projects", json={"name": "My Project"}, headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Project"
    assert "id" in data


async def test_list_projects(test_client: AsyncClient, auth_headers: dict, project_id: str):
    response = await test_client.get("/projects", headers=auth_headers)
    assert response.status_code == 200
    ids = [p["id"] for p in response.json()]
    assert project_id in ids


async def test_get_project(test_client: AsyncClient, auth_headers: dict, project_id: str):
    response = await test_client.get(f"/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == project_id


async def test_get_project_not_found(test_client: AsyncClient, auth_headers: dict):
    response = await test_client.get(f"/projects/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404


async def test_update_project(test_client: AsyncClient, auth_headers: dict, project_id: str):
    response = await test_client.put(
        f"/projects/{project_id}",
        json={"name": "Renamed Project"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Project"


async def test_delete_project(test_client: AsyncClient, auth_headers: dict):
    resp = await test_client.post(
        "/projects", json={"name": "To Delete"}, headers=auth_headers
    )
    pid = resp.json()["id"]

    delete_resp = await test_client.delete(f"/projects/{pid}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = await test_client.get(f"/projects/{pid}", headers=auth_headers)
    assert get_resp.status_code == 404


async def test_project_requires_auth(test_client: AsyncClient):
    response = await test_client.get("/projects")
    assert response.status_code in (401, 403)
