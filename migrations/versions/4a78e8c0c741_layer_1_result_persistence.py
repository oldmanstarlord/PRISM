"""add reproducible Layer 1 result persistence

Revision ID: 4a78e8c0c741
Revises: d8031fcf7da5
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4a78e8c0c741"
down_revision: str | None = "d8031fcf7da5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sector_divergence_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("data_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lookback_start", sa.Date(), nullable=False),
        sa.Column("implementation_version", sa.String(80), nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("score_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("issue_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("exclusion_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "signal_date",
            "implementation_version",
            "configuration_hash",
            "input_fingerprint",
            name="uq_sector_divergence_reproducible_run",
        ),
    )
    op.create_index(
        "ix_sector_divergence_run_latest",
        "sector_divergence_run",
        ["status", "signal_date", "completed_at"],
    )
    op.create_table(
        "sector_divergence_score",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("industry", sa.String(160), nullable=False),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("residual_value", sa.Numeric(24, 16), nullable=False),
        sa.Column("divergence_value", sa.Numeric(24, 12), nullable=False),
        sa.Column("alpha", sa.Numeric(24, 16), nullable=False),
        sa.Column("beta", sa.Numeric(24, 16), nullable=False),
        sa.Column("residual_volatility", sa.Numeric(24, 16), nullable=False),
        sa.Column("industry_percentile", sa.Numeric(8, 4), nullable=False),
        sa.Column("interpretation", sa.String(20), nullable=False),
        sa.Column("lookback_start", sa.Date(), nullable=False),
        sa.Column("lookback_end", sa.Date(), nullable=False),
        sa.Column("observations_used", sa.Integer(), nullable=False),
        sa.Column("membership_source", sa.String(120), nullable=False),
        sa.Column("adjustment_version", sa.String(80), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("horizon IN (1, 5, 20)", name="ck_divergence_score_horizon"),
        sa.ForeignKeyConstraint(["run_id"], ["sector_divergence_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "security_id", "horizon", name="uq_divergence_run_score"),
    )
    op.create_index("ix_sector_divergence_score_run_id", "sector_divergence_score", ["run_id"])
    op.create_index(
        "ix_sector_divergence_score_security_id", "sector_divergence_score", ["security_id"]
    )
    op.create_index(
        "ix_divergence_score_ranking",
        "sector_divergence_score",
        ["run_id", "horizon", "divergence_value"],
    )
    op.create_table(
        "sector_divergence_issue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("horizon", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["sector_divergence_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_divergence_issue_run_stage", "sector_divergence_issue", ["run_id", "stage"])


def downgrade() -> None:
    op.drop_index("ix_divergence_issue_run_stage", table_name="sector_divergence_issue")
    op.drop_table("sector_divergence_issue")
    op.drop_index("ix_divergence_score_ranking", table_name="sector_divergence_score")
    op.drop_index("ix_sector_divergence_score_security_id", table_name="sector_divergence_score")
    op.drop_index("ix_sector_divergence_score_run_id", table_name="sector_divergence_score")
    op.drop_table("sector_divergence_score")
    op.drop_index("ix_sector_divergence_run_latest", table_name="sector_divergence_run")
    op.drop_table("sector_divergence_run")
