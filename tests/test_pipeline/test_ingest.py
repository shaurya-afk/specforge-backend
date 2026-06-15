from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.pipeline.nodes.ingest import ingest_node


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


def _mock_session_local(chunks):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = chunks

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


async def test_ingest_node_returns_chunks():
    chunk = MagicMock()
    chunk.id = uuid4()
    chunk.content = "Users keep asking for dark mode"
    chunk.embedding = [0.1] * 1024

    with patch("app.pipeline.nodes.ingest.AsyncSessionLocal", return_value=_mock_session_local([chunk])):
        result = await ingest_node(_make_state())

    assert result["error"] is None
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["content"] == "Users keep asking for dark mode"
    assert isinstance(result["chunks"][0]["embedding"][0], float)


async def test_ingest_node_no_chunks_returns_error():
    with patch("app.pipeline.nodes.ingest.AsyncSessionLocal", return_value=_mock_session_local([])):
        result = await ingest_node(_make_state())

    assert result["error"] is not None
    assert result["chunks"] == []
