from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.pipeline.nodes.generate import generate_node
from app.schemas.prd import PRDDocument, UserStory


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


def _mock_approved_opportunity():
    opp = MagicMock()
    opp.label = "Dark mode"
    opp.description = "Users want dark mode support"
    opp.total_score = 0.8
    return opp


def _mock_prd_document():
    return PRDDocument(
        summary="A dark mode feature for the application.",
        user_stories=[
            UserStory(
                title="Toggle dark mode",
                as_a="user",
                i_want="to switch to dark mode",
                so_that="my eyes are less strained",
                acceptance_criteria=["Toggle visible", "Preference persists", "System preference respected"],
            )
        ],
        edge_cases=["No system preference set"],
        schema_sketch="users.theme_preference (enum: light|dark|system)",
        claude_code_prompt="Implement dark mode toggle...",
    )


def _mock_session_local_with_opps(approved_opps):
    mock_run = MagicMock()
    mock_run.prd_json = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = approved_opps

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.get = AsyncMock(return_value=mock_run)
    mock_db.commit = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_run


async def test_generate_node_stores_prd():
    mock_cm, mock_run = _mock_session_local_with_opps([_mock_approved_opportunity()])

    with patch(
        "app.pipeline.nodes.generate.structured_completion", new_callable=AsyncMock
    ) as mock_llm, patch(
        "app.pipeline.nodes.generate.AsyncSessionLocal", return_value=mock_cm
    ):
        mock_llm.return_value = _mock_prd_document()
        result = await generate_node(_make_state())

    assert result == {"error": None}
    assert mock_run.prd_json is not None


async def test_generate_node_no_approved_opps():
    mock_cm, mock_run = _mock_session_local_with_opps([])

    with patch(
        "app.pipeline.nodes.generate.AsyncSessionLocal", return_value=mock_cm
    ):
        result = await generate_node(_make_state())

    assert result == {"error": None}
    assert mock_run.prd_json is not None
    assert mock_run.prd_json["summary"] == "No opportunities were approved."


async def test_generate_node_propagates_error_state():
    result = await generate_node(_make_state(error="prior failure"))
    assert result == {}
