import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.opportunity import Opportunity
from app.models.pipeline_run import PipelineRun
from app.pipeline.state import PipelineState
from app.schemas.prd import PRDDocument
from app.services.llm import structured_completion

_SCHEMA_EXAMPLE = """{
  "summary": "<2-3 sentence product overview>",
  "user_stories": [
    {
      "title": "<short title>",
      "as_a": "<user type>",
      "i_want": "<action>",
      "so_that": "<benefit>",
      "acceptance_criteria": ["<criterion 1>", "<criterion 2>", "<criterion 3>"]
    }
  ],
  "edge_cases": ["<edge case 1>", "<edge case 2>"],
  "schema_sketch": "<key data entities and their relationships as prose or a simple table>",
  "claude_code_prompt": "<detailed, self-contained prompt that can be pasted directly into Claude Code to implement this feature>"
}"""


async def generate_node(state: PipelineState) -> dict:
    if state.get("error"):
        return {}

    run_id = uuid.UUID(state["run_id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Opportunity)
            .where(Opportunity.run_id == run_id)
            .where(Opportunity.is_approved == True)  # noqa: E712
            .order_by(Opportunity.total_score.desc())
        )
        approved = result.scalars().all()

        if not approved:
            run = await db.get(PipelineRun, run_id)
            if run:
                run.prd_json = PRDDocument(
                    summary="No opportunities were approved.",
                    user_stories=[],
                    edge_cases=[],
                    schema_sketch="",
                    claude_code_prompt="",
                ).model_dump()
            await db.commit()
            return {"error": None}

        items = "\n".join(
            f"- {o.label}: {o.description}" for o in approved
        )
        prompt = (
            f"You are a senior product manager. Generate a structured PRD for the following "
            f"approved customer needs:\n\n{items}\n\n"
            f"Include 3-5 user stories, each with exactly 3 acceptance criteria. "
            f"The claude_code_prompt should be detailed enough to implement this feature "
            f"from scratch without additional context.\n\n"
            f"Respond as JSON matching this exact structure:\n{_SCHEMA_EXAMPLE}"
        )

        prd: PRDDocument = await structured_completion(
            prompt,
            PRDDocument,
            system="You are a senior product manager. Always respond with valid JSON.",
        )

        run = await db.get(PipelineRun, run_id)
        if run:
            run.prd_json = prd.model_dump()
        await db.commit()

    return {"error": None}
