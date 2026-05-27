import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class BaseModel(Base):
    __tablename__ = "base_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # e.g. "meta-llama/Llama-3.2-3B-Instruct"
    param_count: Mapped[int] = mapped_column(Integer, nullable=False)  # in billions, e.g. 3
    min_vram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    supported_adapters: Mapped[list] = mapped_column(JSONB, default=lambda: ["lora", "qlora"])
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
