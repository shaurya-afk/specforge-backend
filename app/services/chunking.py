import re

_MAX_CHUNK_CHARS = 800
_MIN_CHUNK_CHARS = 30


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= _MAX_CHUNK_CHARS:
            chunks.append(para)
        else:
            chunks.extend(_split_sentences(para))
    return [c for c in chunks if len(c) >= _MIN_CHUNK_CHARS]
