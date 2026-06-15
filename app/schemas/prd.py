import uuid

from pydantic import BaseModel


class UserStory(BaseModel):
    title: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: list[str]


class PRDDocument(BaseModel):
    summary: str
    user_stories: list[UserStory]
    edge_cases: list[str]
    schema_sketch: str
    claude_code_prompt: str


class PRDOut(BaseModel):
    run_id: uuid.UUID
    prd: PRDDocument
