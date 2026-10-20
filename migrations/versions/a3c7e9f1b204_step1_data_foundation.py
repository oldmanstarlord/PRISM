"""Add reproducible NIFTY 200 data-foundation persistence.

Revision ID: a3c7e9f1b204
Revises: f2a3b4c5d6e7
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3c7e9f1b204"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("security", "isin", existing_type=sa.String(12), nullable=True)
    op.add_column("security_alias", sa.Column("provider_symbol", sa.String(80)))
    op.add_column("security_alias", sa.Column("verification_status", sa.String(20)))
    op.add_column("security_alias", sa.Column("verification_reason", sa.Text()))
    op.add_column("security_alias", sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_alias_verification_status",
        "security_alias",
        "verification_status IS NULL OR verification_status IN ('verified', 'failed')",
    )
    op.add_column("price_daily_raw", sa.Column("provider_version", sa.String(80)))
    op.add_column("price_daily_raw", sa.Column("pipeline_run_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_price_daily_raw_pipeline_run",
        "price_daily_raw",
        "pipeline_run",
        ["pipeline_run_id"],
        ["id"],
    )

    op.create_table(
        "market_data_fetch_result",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("provider_symbol", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("requested_start", sa.Date(), nullable=False),
        sa.Column("requested_end", sa.Date(), nullable=False),
        sa.Column("rows_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("full_refetch", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_version", sa.String(80), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.UniqueConstraint("run_id", "security_id", name="uq_market_data_fetch_run_security"),
    )
    op.create_index(
        "ix_market_data_fetch_status", "market_data_fetch_result", ["run_id", "status"]
    )

    op.create_table(
        "data_quality_result",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("reasons", postgresql.JSONB(), nullable=False),
        sa.Column("observations", sa.Integer(), nullable=False),
        sa.Column("expected_sessions", sa.Integer()),
        sa.Column("last_trade_date", sa.Date()),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pass', 'warn', 'fail')", name="ck_quality_status"),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.UniqueConstraint("run_id", "security_id", name="uq_quality_run_security"),
    )
    op.create_index("ix_quality_result_run_status", "data_quality_result", ["run_id", "status"])

    op.create_table(
        "stock_metric_daily",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("volatility_1m", sa.Numeric(20, 12)),
        sa.Column("volatility_3m", sa.Numeric(20, 12)),
        sa.Column("volatility_6m", sa.Numeric(20, 12)),
        sa.Column("volatility_1y", sa.Numeric(20, 12)),
        sa.Column("downside_volatility", sa.Numeric(20, 12)),
        sa.Column("max_drawdown", sa.Numeric(20, 12)),
        sa.Column("beta_nifty50", sa.Numeric(20, 12)),
        sa.Column("average_traded_value_20d", sa.Numeric(24, 6)),
        sa.Column("factor_volatility", sa.Numeric(20, 12)),
        sa.Column("factor_downside", sa.Numeric(20, 12)),
        sa.Column("factor_drawdown", sa.Numeric(20, 12)),
        sa.Column("factor_beta", sa.Numeric(20, 12)),
        sa.Column("factor_instability", sa.Numeric(20, 12)),
        sa.Column("score", sa.Numeric(10, 4)),
        sa.Column("quality_status", sa.String(10), nullable=False),
        sa.Column("observations_used", sa.Integer(), nullable=False),
        sa.Column("missing_reasons", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("methodology_version", sa.String(80), nullable=False),
        sa.Column("source_data_as_of", sa.DateTime(timezone=True)),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quality_status IN ('pass', 'warn', 'fail')", name="ck_metric_quality"
        ),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_run.id"]),
        sa.UniqueConstraint(
            "security_id", "metric_date", "methodology_version", name="uq_stock_metric_daily"
        ),
    )
    op.create_index(
        "ix_stock_metric_date_quality", "stock_metric_daily", ["metric_date", "quality_status"]
    )

    op.create_table(
        "score_calibration",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("calibration_date", sa.Date(), nullable=False),
        sa.Column("factor", sa.String(40), nullable=False),
        sa.Column("lower_percentile", sa.Numeric(8, 6), nullable=False),
        sa.Column("upper_percentile", sa.Numeric(8, 6), nullable=False),
        sa.Column("lower_value", sa.Numeric(24, 12), nullable=False),
        sa.Column("upper_value", sa.Numeric(24, 12), nullable=False),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("methodology_version", sa.String(80), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_run.id"]),
        sa.UniqueConstraint(
            "calibration_date", "factor", "methodology_version", name="uq_score_calibration"
        ),
    )
    op.create_index(
        "ix_score_calibration_calibration_date",
        "score_calibration",
        ["calibration_date"],
    )

    op.create_table(
        "fundamentals_snapshot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("field", sa.String(80), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.UniqueConstraint(
            "security_id", "field", "as_of", "source", name="uq_fundamentals_snapshot"
        ),
    )
    op.create_index(
        "ix_fundamentals_security_fetched",
        "fundamentals_snapshot",
        ["security_id", "fetched_at"],
    )

    op.create_table(
        "data_coverage_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("universe_count", sa.Integer(), nullable=False),
        sa.Column("verified_ticker_count", sa.Integer(), nullable=False),
        sa.Column("enough_history_count", sa.Integer(), nullable=False),
        sa.Column("quality_pass_count", sa.Integer(), nullable=False),
        sa.Column("metrics_ready_count", sa.Integer(), nullable=False),
        sa.Column("fundamentals_ready_count", sa.Integer(), nullable=False),
        sa.Column("excluded_symbols", postgresql.JSONB(), nullable=False),
        sa.Column("spot_checks", postgresql.JSONB(), nullable=False),
        sa.Column("data_date", sa.Date()),
        sa.Column("last_update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "status IN ('completed', 'partial', 'failed')", name="ck_coverage_status"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_run.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", name="uq_data_coverage_pipeline_run"),
    )


def downgrade() -> None:
    op.drop_table("data_coverage_run")
    op.drop_table("fundamentals_snapshot")
    op.drop_table("score_calibration")
    op.drop_table("stock_metric_daily")
    op.drop_table("data_quality_result")
    op.drop_table("market_data_fetch_result")
    op.drop_constraint("fk_price_daily_raw_pipeline_run", "price_daily_raw", type_="foreignkey")
    op.drop_column("price_daily_raw", "pipeline_run_id")
    op.drop_column("price_daily_raw", "provider_version")
    op.drop_constraint("ck_alias_verification_status", "security_alias", type_="check")
    op.drop_column("security_alias", "verified_at")
    op.drop_column("security_alias", "verification_reason")
    op.drop_column("security_alias", "verification_status")
    op.drop_column("security_alias", "provider_symbol")
    op.alter_column("security", "isin", existing_type=sa.String(12), nullable=False)
