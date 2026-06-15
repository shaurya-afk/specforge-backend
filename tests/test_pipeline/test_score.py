from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.pipeline.nodes.score import SeverityScore, score_node


def _make_state(**kwargs):
    chunk_id = str(uuid4())
    return {
        "project_id": str(uuid4()),
        "run_id": str(uuid4()),
        "chunks": [{"id": chunk_id, "content": "Users want dark mode", "embedding": [0.1] * 1024}],
        "clusters": [{"label": "Dark mode", "description": "Users want dark mode", "chunk_ids": [chunk_id]}],
        "opportunities": [],
        "error": None,
        **kwargs,
    }


def _mock_session_local():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=AsyncMock())
    mock_db.add_all = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


async def test_score_node_computes_total_score():
    with patch(
        "app.pipeline.nodes.score.structured_completion", new_callable=AsyncMock
    ) as mock_llm, patch(
        "app.pipeline.nodes.score.AsyncSessionLocal", return_value=_mock_session_local()
    ):
        mock_llm.return_value = SeverityScore(severity=8, rationale="Significant pain point")
        result = await score_node(_make_state())

    assert "opportunities" in result
    assert len(result["opportunities"]) == 1
    opp = result["opportunities"][0]
    assert opp["severity_score"] == 8.0
    assert opp["frequency_score"] == 1.0  # 1 chunk in cluster / 1 total chunk
    expected_total = round(0.6 * 1.0 + 0.4 * (8 / 10), 4)
    assert opp["total_score"] == expected_total


async def test_score_node_propagates_error_state():
    result = await score_node(_make_state(error="prior failure"))
    assert result == {}
