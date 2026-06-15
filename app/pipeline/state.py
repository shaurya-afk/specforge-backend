from typing import TypedDict


class PipelineState(TypedDict):
    project_id: str
    run_id: str
    chunks: list[dict]         # {id: str, content: str, embedding: list[float]}
    clusters: list[dict]       # {label: str, description: str, chunk_ids: list[str]}
    opportunities: list[dict]  # {id: str, label, description, frequency_score, severity_score, total_score}
    error: str | None
