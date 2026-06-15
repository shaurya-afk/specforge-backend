import numpy as np
from pydantic import BaseModel

from app.pipeline.state import PipelineState
from app.services.llm import structured_completion

_SIMILARITY_THRESHOLD = 0.72
_MAX_SAMPLE_CHUNKS = 5


class ClusterLabel(BaseModel):
    label: str
    description: str


def _cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / (norms + 1e-8)
    return normalized @ normalized.T


def _greedy_cluster(sim_matrix: np.ndarray, threshold: float) -> list[list[int]]:
    n = sim_matrix.shape[0]
    assigned = [False] * n
    clusters: list[list[int]] = []

    for i in range(n):
        if assigned[i]:
            continue
        cluster = [i]
        assigned[i] = True
        for j in range(i + 1, n):
            if not assigned[j] and sim_matrix[i, j] >= threshold:
                cluster.append(j)
                assigned[j] = True
        clusters.append(cluster)

    return clusters


async def cluster_node(state: PipelineState) -> dict:
    if state.get("error"):
        return {}

    chunks = state["chunks"]
    embeddings = np.array([c["embedding"] for c in chunks], dtype=np.float32)
    sim_matrix = _cosine_similarity_matrix(embeddings)
    raw_clusters = _greedy_cluster(sim_matrix, _SIMILARITY_THRESHOLD)

    labeled: list[dict] = []
    for indices in raw_clusters:
        samples = [chunks[i]["content"] for i in indices[:_MAX_SAMPLE_CHUNKS]]
        excerpts = "\n---\n".join(samples)
        prompt = (
            f"The following customer feedback excerpts belong to the same theme:\n\n"
            f"{excerpts}\n\n"
            f"Provide a concise label (3-6 words) and a one-sentence description of this theme. "
            f'Respond as JSON: {{"label": "...", "description": "..."}}'
        )
        result: ClusterLabel = await structured_completion(prompt, ClusterLabel)
        labeled.append(
            {
                "label": result.label,
                "description": result.description,
                "chunk_ids": [chunks[i]["id"] for i in indices],
            }
        )

    return {"clusters": labeled}
