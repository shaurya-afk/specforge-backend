import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.pipeline_run import PipelineRun
from app.models.project import Project
from app.models.user import User
from app.schemas.prd import PRDDocument, PRDOut, UserStory

router = APIRouter(
    prefix="/projects/{project_id}/pipeline/{run_id}/prd",
    tags=["prd"],
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


async def _get_completed_run(
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
    if run.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PRD not available — run is '{run.status}'",
        )
    if not run.prd_json:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PRD not found")
    return run


def _to_markdown(prd: PRDDocument) -> str:
    lines: list[str] = ["# Product Requirements Document", "", "## Summary", "", prd.summary, ""]

    lines += ["## User Stories", ""]
    for i, story in enumerate(prd.user_stories, 1):
        lines += [
            f"### {i}. {story.title}",
            "",
            f"**As a** {story.as_a}, **I want to** {story.i_want}, **so that** {story.so_that}",
            "",
            "**Acceptance Criteria:**",
        ]
        for ac in story.acceptance_criteria:
            lines.append(f"- {ac}")
        lines.append("")

    lines += ["## Edge Cases", ""]
    for ec in prd.edge_cases:
        lines.append(f"- {ec}")
    lines.append("")

    lines += ["## Schema Sketch", "", prd.schema_sketch, ""]

    lines += ["## Claude Code Prompt", "", "```", prd.claude_code_prompt, "```", ""]

    return "\n".join(lines)


@router.get("/", response_model=PRDOut)
async def get_prd(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PRDOut:
    await _get_project_or_404(project_id, current_user, db)
    run = await _get_completed_run(run_id, project_id, db)
    prd = PRDDocument.model_validate(run.prd_json)
    return PRDOut(run_id=run.id, prd=prd)


@router.get("/export", response_class=PlainTextResponse)
async def export_prd_markdown(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    await _get_project_or_404(project_id, current_user, db)
    run = await _get_completed_run(run_id, project_id, db)
    prd = PRDDocument.model_validate(run.prd_json)
    return _to_markdown(prd)
