"""GNN point-in-time classifications and persisted structural drift.

Revision ID: f6a1b2c3d4e5
Revises: c5e9f3b7a402
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a1b2c3d4e5"
down_revision: str | None = "c5e9f3b7a402"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_industry_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("security_id", sa.UUID(), nullable=False),
        sa.Column("industry", sa.String(length=160), nullable=False),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_industry_dates"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "security_id", "valid_from", name="uq_security_industry_history_period"
        ),
    )
    op.create_index(
        "ix_security_industry_history_security_id", "security_industry_history", ["security_id"]
    )
    op.create_index(
        "ix_security_industry_history_security_dates",
        "security_industry_history",
        ["security_id", "valid_from"],
    )
    op.create_table(
        "gnn_stock_drift",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("industry", sa.String(length=160), nullable=False),
        sa.Column("embedding_drift", sa.Numeric(16, 8), nullable=False),
        sa.Column("drift_percentile", sa.Numeric(8, 6), nullable=False),
        sa.Column("alert_level", sa.String(length=20), nullable=False),
        sa.Column("primary_driver", sa.String(length=80), nullable=True),
        sa.Column("driver_scope", sa.String(length=30), nullable=True),
        sa.Column(
            "driver_scores",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "explanation",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "drift_percentile >= 0 AND drift_percentile <= 1", name="ck_gnn_drift_percentile"
        ),
        sa.CheckConstraint(
            "alert_level IN ('normal', 'elevated', 'high')", name="ck_gnn_alert_level"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["model_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "analysis_date", "symbol", name="uq_gnn_stock_drift_run_date_symbol"
        ),
    )
    op.create_index(
        "ix_gnn_stock_drift_date_level", "gnn_stock_drift", ["analysis_date", "alert_level"]
    )
    op.create_index(
        "ix_gnn_stock_drift_symbol_date", "gnn_stock_drift", ["symbol", "analysis_date"]
    )
    op.create_table(
        "gnn_market_drift",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("analysis_date", sa.Date(), nullable=False),
        sa.Column("mean_drift", sa.Numeric(16, 8), nullable=False),
        sa.Column("share_above_train_95pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("active_stocks", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["model_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "analysis_date", name="uq_gnn_market_drift_run_date"),
    )
    op.create_index("ix_gnn_market_drift_date", "gnn_market_drift", ["analysis_date"])


def downgrade() -> None:
    op.drop_index("ix_gnn_market_drift_date", table_name="gnn_market_drift")
    op.drop_table("gnn_market_drift")
    op.drop_index("ix_gnn_stock_drift_symbol_date", table_name="gnn_stock_drift")
    op.drop_index("ix_gnn_stock_drift_date_level", table_name="gnn_stock_drift")
    op.drop_table("gnn_stock_drift")
    op.drop_index(
        "ix_security_industry_history_security_dates", table_name="security_industry_history"
    )
    op.drop_index(
        "ix_security_industry_history_security_id", table_name="security_industry_history"
    )
    op.drop_table("security_industry_history")
