import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.opportunity import Opportunity
from app.models.pipeline_run import PipelineRun
from app.models.project import Project
from app.models.user import User
from app.schemas.pipeline import OpportunityOut, OpportunityUpdate

router = APIRouter(
    prefix="/projects/{project_id}/pipeline/{run_id}/opportunities",
    tags=["opportunities"],
)


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


async def _get_run_or_404(
    run_id: uuid.UUID,
    project_id: uuid.UUID,
    db: AsyncSession,
) -> PipelineRun:
    result = await db.execute(
        select(PipelineRun).where(
            PipelineRun.id == run_id,
            PipelineRun.project_id == project_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    return run


@router.get("/", response_model=list[OpportunityOut])
async def list_opportunities(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Opportunity]:
    await _get_project_or_404(project_id, current_user, db)
    await _get_run_or_404(run_id, project_id, db)

    result = await db.execute(
        select(Opportunity)
        .where(Opportunity.run_id == run_id)
        .order_by(Opportunity.total_score.desc())
    )
    return list(result.scalars().all())


@router.patch("/{opportunity_id}", response_model=OpportunityOut)
async def edit_opportunity(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    body: OpportunityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Opportunity:
    await _get_project_or_404(project_id, current_user, db)
    run = await _get_run_or_404(run_id, project_id, db)

    if run.status != "awaiting_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit opportunities while run is '{run.status}'",
        )

    result = await db.execute(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.run_id == run_id,
        )
    )
    opp = result.scalar_one_or_none()
    if opp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    if body.label is not None:
        opp.label = body.label
    if body.description is not None:
        opp.description = body.description
    if body.severity_score is not None:
        opp.severity_score = body.severity_score
        opp.total_score = round(0.6 * opp.frequency_score + 0.4 * (body.severity_score / 10), 4)
    if body.is_approved is not None:
        opp.is_approved = body.is_approved

    await db.commit()
    await db.refresh(opp)
    return opp
