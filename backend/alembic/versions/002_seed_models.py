"""Seed data for base models

Revision ID: 002_seed_models
Revises: 001_initial
Create Date: 2026-05-25

"""
from alembic import op
from sqlalchemy import text

revision = "002_seed_models"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    models = [
        # (name, param_count, min_vram_gb)
        ("unsloth/Llama-3.2-3B-Instruct", 3, 8),
        ("meta-llama/Llama-3.1-8B-Instruct", 8, 16),
        ("mistralai/Mistral-7B-v0.3", 7, 16),
        ("Qwen/Qwen2.5-7B-Instruct", 7, 16),
        ("meta-llama/Llama-3.1-70B-Instruct", 70, 80),
    ]
    for name, params, vram in models:
        conn.execute(text(
            "INSERT INTO base_models (name, param_count, min_vram_gb) VALUES (:name, :params, :vram) ON CONFLICT (name) DO NOTHING"
        ), {"name": name, "params": params, "vram": vram})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DELETE FROM base_models"))
