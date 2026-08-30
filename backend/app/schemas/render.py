from datetime import datetime

from pydantic import BaseModel


class CreateRenderJobRequest(BaseModel):
    file_id: int


class RenderJobPublic(BaseModel):
    id: int
    file_id: int
    status: str
    error: str | None = None
    output_size_bytes: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    has_output: bool = False

    model_config = {"from_attributes": True}
