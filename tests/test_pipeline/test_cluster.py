from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.pipeline.nodes.cluster import ClusterLabel, cluster_node


def _make_state(**kwargs):
    return {
        "project_id": str(uuid4()),
        "run_id": str(uuid4()),
        "chunks": [],
        "clusters": [],
        "opportunities": [],
        "error": None,
        **kwargs,
    }


def _make_chunks(n: int = 3) -> list[dict]:
    return [
        {"id": str(uuid4()), "content": f"Feedback chunk {i}", "embedding": [float(i) / 10] * 1024}
        for i in range(n)
    ]


async def test_cluster_node_groups_chunks():
    chunks = _make_chunks(3)
    with patch(
        "app.pipeline.nodes.cluster.structured_completion", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = ClusterLabel(label="Dark mode", description="Users want dark mode")
        result = await cluster_node(_make_state(chunks=chunks))

    assert "clusters" in result
    assert len(result["clusters"]) >= 1
    assert result["clusters"][0]["label"] == "Dark mode"
    assert "chunk_ids" in result["clusters"][0]


async def test_cluster_node_propagates_error_state():
    result = await cluster_node(_make_state(error="prior failure"))
    assert result == {}
