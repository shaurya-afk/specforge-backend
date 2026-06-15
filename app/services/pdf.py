import io

from pypdf import PdfReader


def extract_text(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Could not parse PDF: {exc}") from exc
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()
