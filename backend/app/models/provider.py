from datetime import datetime, timezone

from sqlalchemy import Integer, String
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
