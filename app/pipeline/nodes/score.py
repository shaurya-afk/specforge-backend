import uuid

from pydantic import BaseModel
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.models.opportunity import Opportunity
from app.pipeline.state import PipelineState
from app.services.llm import structured_completion

_MAX_SAMPLE_CHUNKS = 3


class SeverityScore(BaseModel):
    severity: int
    rationale: str


async def score_node(state: PipelineState) -> dict:
    if state.get("error"):
        return {}

    clusters = state["clusters"]
    chunks = state["chunks"]
    chunk_map = {c["id"]: c["content"] for c in chunks}
    total_chunks = len(chunks)
    run_id = uuid.UUID(state["run_id"])

    scored: list[dict] = []
    for cluster in clusters:
        frequency_score = len(cluster["chunk_ids"]) / total_chunks

        samples = [
            chunk_map[cid]
            for cid in cluster["chunk_ids"][:_MAX_SAMPLE_CHUNKS]
            if cid in chunk_map
        ]
        excerpts = "\n---\n".join(samples)
        prompt = (
            f"Rate the customer pain severity (1-10) for this feedback theme:\n\n"
            f"Theme: {cluster['label']}\n\n"
            f"Sample feedback:\n{excerpts}\n\n"
            f"10 = critical blocker, 1 = minor inconvenience. "
            f'Respond as JSON: {{"severity": <int>, "rationale": "<one sentence>"}}'
        )
        severity_result: SeverityScore = await structured_completion(prompt, SeverityScore)
        severity = max(1, min(10, severity_result.severity))

        total_score = round(0.6 * frequency_score + 0.4 * (severity / 10), 4)
        scored.append(
            {
                "label": cluster["label"],
                "description": cluster["description"],
                "chunk_ids": cluster["chunk_ids"],
                "frequency_score": round(frequency_score, 4),
                "severity_score": float(severity),
                "total_score": total_score,
            }
        )

    scored.sort(key=lambda x: x["total_score"], reverse=True)

    async with AsyncSessionLocal() as db:
        await db.execute(delete(Opportunity).where(Opportunity.run_id == run_id))
        rows = [
            Opportunity(
                run_id=run_id,
                label=o["label"],
                description=o["description"],
                chunk_ids=o["chunk_ids"],
                frequency_score=o["frequency_score"],
                severity_score=o["severity_score"],
                total_score=o["total_score"],
                is_approved=None,
            )
            for o in scored
        ]
        db.add_all(rows)
        await db.commit()
        for row in rows:
            await db.refresh(row)

    return {
        "opportunities": [
            {**o, "id": str(rows[i].id)}
            for i, o in enumerate(scored)
        ]
    }
