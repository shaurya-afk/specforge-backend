import voyageai

from app.core.config import get_settings

_client: voyageai.AsyncClient | None = None


def _get_client() -> voyageai.AsyncClient:
    global _client
    if _client is None:
        _client = voyageai.AsyncClient(api_key=get_settings().VOYAGE_API_KEY)
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    result = await _get_client().embed(texts, model="voyage-3", input_type="document")
    return result.embeddings
