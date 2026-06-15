import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.database import AsyncSessionLocal
from app.models.signal import Signal
from app.models.signal_chunk import SignalChunk
from app.pipeline.state import PipelineState


async def ingest_node(state: PipelineState) -> dict:
    project_id = uuid.UUID(state["project_id"])

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SignalChunk)
            .join(Signal, SignalChunk.signal_id == Signal.id)
            .where(Signal.project_id == project_id)
            .where(SignalChunk.embedding.is_not(None))
            .order_by(SignalChunk.created_at)
        )
        chunks = result.scalars().all()

    if not chunks:
        return {"chunks": [], "error": "No embedded chunks found for this project."}

    return {
        "chunks": [
            {
                "id": str(c.id),
                "content": c.content,
                "embedding": [float(v) for v in c.embedding],
            }
            for c in chunks
        ],
        "error": None,
    }
