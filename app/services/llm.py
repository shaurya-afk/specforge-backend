from groq import AsyncGroq
from pydantic import BaseModel

from app.core.config import get_settings

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=get_settings().GROQ_API_KEY)
    return _client


async def structured_completion(
    prompt: str,
    schema: type[BaseModel],
    system: str = "You are a helpful assistant. Always respond with valid JSON.",
) -> BaseModel:
    response = await _get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw = response.choices[0].message.content
    return schema.model_validate_json(raw)
