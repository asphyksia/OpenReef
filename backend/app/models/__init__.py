from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models so Alembic picks them up in metadata
from app.models import user, dataset, job, credit_ledger, base_model, provider  # noqa: F401
