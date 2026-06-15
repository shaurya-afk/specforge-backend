import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class PipelineRunOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    error_msg: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    label: str
    description: str
    chunk_ids: list[str]
    frequency_score: float
    severity_score: float
    total_score: float
    is_approved: bool | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OpportunityUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    severity_score: float | None = None
    is_approved: bool | None = None

    @field_validator("severity_score")
    @classmethod
    def validate_severity(cls, v: float | None) -> float | None:
        if v is not None and not (1 <= v <= 10):
            raise ValueError("severity_score must be between 1 and 10")
        return v


class PipelineStatusOut(BaseModel):
    run_id: uuid.UUID
    status: str
    error_msg: str | None
    opportunities: list[OpportunityOut]
