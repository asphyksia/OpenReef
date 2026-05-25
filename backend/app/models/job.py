import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

JOB_STATUSES = (
    "pending",
    "validating",
    "queued",
    "provisioning",
    "running",
    "checkpointing",
    "completed",
    "failed",
    "cancelled",
    "refunded",
)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    base_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("base_models.id"), nullable=False)
    preset: Mapped[str] = mapped_column(String(20), nullable=False)  # fast, balanced, quality
    adapter: Mapped[str] = mapped_column(String(10), nullable=False)  # lora, qlora
    status: Mapped[str] = mapped_column(String(20), default="pending")
    status_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    actual_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    ogpu_task_address: Mapped[str | None] = mapped_column(String(255), nullable=True)  # on-chain task address
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_r2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    progress_pct: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
