import uuid
from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    dataset_id: uuid.UUID
    base_model_id: uuid.UUID
    preset: str  # fast, balanced, quality
    adapter: str  # lora, qlora


class JobResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    base_model_id: uuid.UUID
    preset: str
    adapter: str
    status: str
    status_detail: str | None
    estimated_cost: float | None
    actual_cost: float | None
    progress_pct: int
    estimated_completion: str | None = None
    error_message: str | None
    ogpu_task_address: str | None
    requeue_count: int
    provider_address: str | None
    download_url: str | None = None
    created_at: str
    started_at: str | None
    completed_at: str | None

    model_config = {"from_attributes": True}
