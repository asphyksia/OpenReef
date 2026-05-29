from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Provider(Base):
    __tablename__ = "providers"

    address: Mapped[str] = mapped_column(String(255), primary_key=True)
    last_active: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    abandoned_count: Mapped[int] = mapped_column(Integer, default=0)
    last_abandoned_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # SmartRoute — hardware info
    environment: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=CPU, 2=NVIDIA, 4=AMD
    gpu_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vram_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ram_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    base_data_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_sync: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
