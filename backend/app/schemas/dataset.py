import uuid
from pydantic import BaseModel


class DatasetResponse(BaseModel):
    id: uuid.UUID
    name: str
    filename: str
    format: str
    size_bytes: int
    row_count: int | None
    validation_status: str
    validation_errors: list
    created_at: str

    model_config = {"from_attributes": True}
