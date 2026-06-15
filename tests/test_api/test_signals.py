from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

_FAKE_EMBEDDING = [[0.1] * 1024]

# Minimal valid single-page PDF
_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
    b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\n"
    b"BT /F1 12 Tf 100 700 Td (Hello World) Tj ET\n"
    b"endstream\nendobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"xref\n0 6\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"0000000274 00000 n \n"
    b"0000000370 00000 n \n"
    b"trailer<</Size 6/Root 1 0 R>>\n"
    b"startxref\n441\n%%EOF"
)


async def test_ingest_text_success(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    with patch("app.routers.signals.embed_texts", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = _FAKE_EMBEDDING
        response = await test_client.post(
            f"/projects/{project_id}/signals/text",
            json={"content": "Users are asking for dark mode support in the application."},
            headers=auth_headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert data["chunk_count"] >= 1
    assert data["source_type"] == "text"


async def test_ingest_empty_text(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    with patch("app.routers.signals.embed_texts", new_callable=AsyncMock):
        response = await test_client.post(
            f"/projects/{project_id}/signals/text",
            json={"content": ""},
            headers=auth_headers,
        )
    assert response.status_code == 422


async def test_ingest_text_no_usable_chunks(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    with patch("app.routers.signals.embed_texts", new_callable=AsyncMock):
        response = await test_client.post(
            f"/projects/{project_id}/signals/text",
            json={"content": "hi"},
            headers=auth_headers,
        )
    assert response.status_code == 422


async def test_ingest_pdf_success(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    with patch("app.routers.signals.embed_texts", new_callable=AsyncMock) as mock_embed, \
         patch("app.routers.signals.extract_text", return_value="Users want dark mode. The app needs this feature.") as _mock_extract:
        mock_embed.return_value = _FAKE_EMBEDDING
        response = await test_client.post(
            f"/projects/{project_id}/signals/upload",
            files={"file": ("test.pdf", _MINIMAL_PDF, "application/pdf")},
            headers=auth_headers,
        )
    assert response.status_code == 201
    assert response.json()["source_type"] == "pdf"


async def test_ingest_pdf_wrong_content_type(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    response = await test_client.post(
        f"/projects/{project_id}/signals/upload",
        files={"file": ("test.txt", b"some text", "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_ingest_malformed_pdf(
    test_client: AsyncClient, auth_headers: dict, project_id: str
):
    with patch("app.routers.signals.embed_texts", new_callable=AsyncMock):
        response = await test_client.post(
            f"/projects/{project_id}/signals/upload",
            files={"file": ("bad.pdf", b"this is not a pdf", "application/pdf")},
            headers=auth_headers,
        )
    assert response.status_code == 422
