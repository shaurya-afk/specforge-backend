import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.core.limiter import limiter
from app.core.security import get_current_user
from app.models.opportunity import Opportunity
from app.models.pipeline_run import PipelineRun
from app.models.project import Project
from app.models.user import User
from app.pipeline.graph import pipeline_graph
from app.schemas.pipeline import (
    OpportunityOut,
    PipelineRunOut,
    PipelineStatusOut,
)

router = APIRouter(prefix="/projects/{project_id}/pipeline", tags=["pipeline"])


async def _get_project_or_404(
    project_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _execute_pipeline(run_id: str, project_id: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await db.get(PipelineRun, uuid.UUID(run_id))
        if run:
            run.status = "running"
            await db.commit()

    config = {"configurable": {"thread_id": run_id}}
    initial_state = {
        "project_id": project_id,
        "run_id": run_id,
        "chunks": [],
        "clusters": [],
        "opportunities": [],
        "error": None,
    }

    try:
        async for _ in pipeline_graph.astream(initial_state, config=config):
            pass

        async with AsyncSessionLocal() as db:
            run = await db.get(PipelineRun, uuid.UUID(run_id))
            if run:
                final_state = pipeline_graph.get_state(config)
                if final_state.values.get("error"):
                    run.status = "failed"
                    run.error_msg = final_state.values["error"]
                else:
                    run.status = "awaiting_approval"
                await db.commit()

    except Exception as exc:
        async with AsyncSessionLocal() as db:
            run = await db.get(PipelineRun, uuid.UUID(run_id))
            if run:
                run.status = "failed"
                run.error_msg = str(exc)
                await db.commit()


async def _resume_pipeline(run_id: str) -> None:
    async with AsyncSessionLocal() as db:
        run = await db.get(PipelineRun, uuid.UUID(run_id))
        if run:
            run.status = "generating"
            await db.commit()

    config = {"configurable": {"thread_id": run_id}}

    try:
        async for _ in pipeline_graph.astream(None, config=config):
            pass

        async with AsyncSessionLocal() as db:
            run = await db.get(PipelineRun, uuid.UUID(run_id))
            if run:
                run.status = "completed"
                await db.commit()

    except Exception as exc:
        async with AsyncSessionLocal() as db:
            run = await db.get(PipelineRun, uuid.UUID(run_id))
            if run:
                run.status = "failed"
                run.error_msg = str(exc)
                await db.commit()


@router.post("/run", response_model=PipelineRunOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def trigger_pipeline(
    request: Request,
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineRun:
    await _get_project_or_404(project_id, current_user, db)

    run = PipelineRun(project_id=project_id, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(_execute_pipeline, str(run.id), str(project_id))
    return run


@router.get("/{run_id}/status", response_model=PipelineStatusOut)
async def get_pipeline_status(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineStatusOut:
    await _get_project_or_404(project_id, current_user, db)

    result = await db.execute(
        select(PipelineRun).where(
            PipelineRun.id == run_id,
            PipelineRun.project_id == project_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")

    opportunities: list[OpportunityOut] = []
    if run.status in ("awaiting_approval", "generating", "completed"):
        opp_result = await db.execute(
            select(Opportunity)
            .where(Opportunity.run_id == run_id)
            .order_by(Opportunity.total_score.desc())
        )
        opps = opp_result.scalars().all()
        opportunities = [OpportunityOut.model_validate(o) for o in opps]

    return PipelineStatusOut(
        run_id=run.id,
        status=run.status,
        error_msg=run.error_msg,
        opportunities=opportunities,
    )


@router.post("/{run_id}/approve", status_code=status.HTTP_200_OK)
async def resume_pipeline(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_project_or_404(project_id, current_user, db)

    result = await db.execute(
        select(PipelineRun).where(
            PipelineRun.id == run_id,
            PipelineRun.project_id == project_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline run is '{run.status}', not awaiting approval",
        )

    approved_count_result = await db.execute(
        select(Opportunity).where(
            Opportunity.run_id == run_id,
            Opportunity.is_approved == True,  # noqa: E712
        )
    )
    if not approved_count_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No opportunities are approved. Approve at least one before resuming.",
        )

    background_tasks.add_task(_resume_pipeline, str(run_id))
    return {"status": "generating"}
