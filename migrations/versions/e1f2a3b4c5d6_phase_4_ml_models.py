"""add model_run and model_prediction tables for Phase 4 ML risk models

Revision ID: e1f2a3b4c5d6
Revises: d9e1f2a3b4c5
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d9e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(80), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("data_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_window_start", sa.Date(), nullable=False),
        sa.Column("training_window_end", sa.Date(), nullable=False),
        sa.Column(
            "features", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column(
            "hyperparameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), server_default="completed", nullable=False),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_run_name_version", "model_run", ["model_name", "model_version"])
    op.create_index("ix_model_run_status_cutoff", "model_run", ["status", "data_cutoff"])
    op.create_index("ix_model_run_name", "model_run", ["model_name"])

    op.create_table(
        "model_prediction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=True),
        sa.Column("security_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(40), nullable=True),
        sa.Column("prediction_date", sa.Date(), nullable=False),
        sa.Column("predicted_value", sa.Numeric(16, 6), nullable=False),
        sa.Column("lower_bound", sa.Numeric(16, 6), nullable=True),
        sa.Column("upper_bound", sa.Numeric(16, 6), nullable=True),
        sa.Column("confidence_level", sa.Numeric(6, 4), nullable=True),
        sa.Column("baseline_value", sa.Numeric(16, 6), nullable=True),
        sa.Column("model_selected", sa.String(40), server_default="ml_model", nullable=False),
        sa.Column(
            "explanation",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["model_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_model_prediction_run_target",
        "model_prediction",
        ["run_id", "target_type"],
    )
    op.create_index(
        "ix_model_prediction_date_symbol",
        "model_prediction",
        ["prediction_date", "symbol"],
    )
    op.create_index("ix_model_prediction_portfolio", "model_prediction", ["portfolio_id"])
    op.create_index("ix_model_prediction_run_id", "model_prediction", ["run_id"])


def downgrade() -> None:
    op.drop_table("model_prediction")
    op.drop_table("model_run")
