import uuid
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.models.opportunity import Opportunity
from app.models.pipeline_run import PipelineRun


async def test_trigger_pipeline_creates_run(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    with patch("app.routers.pipeline._execute_pipeline", new_callable=AsyncMock):
        response = await test_client.post(
            f"/projects/{project_id}/pipeline/run",
            headers=auth_headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert "id" in data


async def test_get_status_not_found(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    response = await test_client.get(
        f"/projects/{project_id}/pipeline/{uuid.uuid4()}/status",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_approve_run_wrong_status(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    async with AsyncSessionLocal() as db:
        run = PipelineRun(project_id=uuid.UUID(project_id), status="pending")
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

    response = await test_client.post(
        f"/projects/{project_id}/pipeline/{run_id}/approve",
        headers=auth_headers,
    )
    assert response.status_code == 409


async def test_approve_run_no_approved_opps(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    async with AsyncSessionLocal() as db:
        run = PipelineRun(project_id=uuid.UUID(project_id), status="awaiting_approval")
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

        opp = Opportunity(
            run_id=run_id,
            label="Dark mode",
            description="Users want dark mode",
            chunk_ids=[],
            frequency_score=0.5,
            severity_score=7.0,
            total_score=0.58,
            is_approved=None,
        )
        db.add(opp)
        await db.commit()

    response = await test_client.post(
        f"/projects/{project_id}/pipeline/{run_id}/approve",
        headers=auth_headers,
    )
    assert response.status_code == 422
