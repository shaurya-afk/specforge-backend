import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SignalPasteRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class SignalOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    source_type: str
    filename: str | None
    created_at: datetime
    chunk_count: int

    model_config = ConfigDict(from_attributes=True)
