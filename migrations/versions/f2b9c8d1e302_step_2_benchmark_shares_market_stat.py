"""Step 2 benchmark series, shares count, market stats, and crosscheck schema.

Revision ID: f2b9c8d1e302
Revises: e1a8b9c7f201
Create Date: 2026-10-05 00:15:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2b9c8d1e302"
down_revision: str | None = "e1a8b9c7f201"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. benchmark_definition
    op.create_table(
        "benchmark_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("benchmark_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("benchmark_id", name="uq_benchmark_definition_id"),
    )
    op.create_index("ix_benchmark_def_id", "benchmark_definition", ["benchmark_id"])

    # 2. benchmark_series
    op.create_table(
        "benchmark_series",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("benchmark_id", sa.String(80), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(20, 6), nullable=True),
        sa.Column("high", sa.Numeric(20, 6), nullable=True),
        sa.Column("low", sa.Numeric(20, 6), nullable=True),
        sa.Column("close", sa.Numeric(20, 6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("source_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "method_version", sa.String(80), server_default="official_daily_v1", nullable=False
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "quality_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_id"],
            ["benchmark_definition.benchmark_id"],
            name="fk_benchmark_series_benchmark_id",
        ),
        sa.UniqueConstraint(
            "benchmark_id",
            "trade_date",
            "source",
            "source_revision",
            name="uq_benchmark_series_revision",
        ),
    )
    op.create_index("ix_benchmark_series_id", "benchmark_series", ["benchmark_id"])
    op.create_index("ix_benchmark_series_date", "benchmark_series", ["trade_date"])
    op.create_index(
        "ix_benchmark_series_id_date", "benchmark_series", ["benchmark_id", "trade_date"]
    )

    # 3. security_share_count
    op.create_table(
        "security_share_count",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("shares_outstanding", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["security.id"],
            name="fk_security_share_count_sec_id",
        ),
        sa.UniqueConstraint(
            "security_id",
            "as_of",
            "source",
            name="uq_security_share_count_period",
        ),
    )
    op.create_index("ix_security_share_count_sec", "security_share_count", ["security_id"])
    op.create_index("ix_security_share_count_as_of", "security_share_count", ["as_of"])
    op.create_index(
        "ix_security_share_count_sec_date",
        "security_share_count",
        ["security_id", "as_of"],
    )

    # 4. security_market_stat
    op.create_table(
        "security_market_stat",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("traded_value", sa.Numeric(24, 4), nullable=False),
        sa.Column("adv_20", sa.Numeric(24, 4), nullable=True),
        sa.Column("market_cap", sa.Numeric(24, 4), nullable=True),
        sa.Column("shares_used", sa.BigInteger(), nullable=True),
        sa.Column("shares_as_of", sa.Date(), nullable=True),
        sa.Column(
            "flags", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["security.id"],
            name="fk_security_market_stat_sec_id",
        ),
        sa.UniqueConstraint("security_id", "trade_date", name="uq_security_market_stat_date"),
    )
    op.create_index("ix_security_market_stat_sec", "security_market_stat", ["security_id"])
    op.create_index("ix_security_market_stat_date", "security_market_stat", ["trade_date"])

    # 5. data_crosscheck
    op.create_table(
        "data_crosscheck",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("source_a", sa.String(60), nullable=False),
        sa.Column("source_b", sa.String(60), nullable=False),
        sa.Column("close_a", sa.Numeric(20, 6), nullable=False),
        sa.Column("close_b", sa.Numeric(20, 6), nullable=False),
        sa.Column("rel_diff", sa.Numeric(12, 8), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["security.id"],
            name="fk_data_crosscheck_sec_id",
        ),
        sa.UniqueConstraint(
            "run_id",
            "security_id",
            "trade_date",
            name="uq_data_crosscheck_run_sec_date",
        ),
    )
    op.create_index("ix_data_crosscheck_run_id", "data_crosscheck", ["run_id"])
    op.create_index("ix_data_crosscheck_status", "data_crosscheck", ["status"])
    op.create_index("ix_data_crosscheck_sec_date", "data_crosscheck", ["security_id", "trade_date"])

    # Seed benchmark_definition: NIFTY_200
    now = datetime.now(UTC)
    bench_table = sa.table(
        "benchmark_definition",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("benchmark_id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("currency", sa.String),
        sa.column("source", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        bench_table,
        [
            {
                "id": uuid4(),
                "benchmark_id": "NIFTY_200",
                "name": "Nifty 200 Index",
                "description": (
                    "NSE India Nifty 200 broad market index daily total return benchmark series."
                ),
                "currency": "INR",
                "source": "NIFTY_INDICES",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("data_crosscheck")
    op.drop_table("security_market_stat")
    op.drop_table("security_share_count")
    op.drop_table("benchmark_series")
    op.drop_table("benchmark_definition")
