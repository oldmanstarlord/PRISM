"""Step 3 portfolio schema and analytics artifact persistence.

Revision ID: c3d4e5f6a703
Revises: f2b9c8d1e302
Create Date: 2026-10-05 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a703"
down_revision: str | None = "f2b9c8d1e302"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. portfolio
    op.create_table(
        "portfolio",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "owner_ref",
            sa.String(120),
            server_default="local-user",
            nullable=False,
        ),
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
    )
    op.create_index("ix_portfolio_owner_ref", "portfolio", ["owner_ref"])

    # 2. portfolio_holding
    op.create_table(
        "portfolio_holding",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=True),
        sa.Column("weight", sa.Numeric(12, 8), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("source", sa.String(80), server_default="manual_entry", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolio.id"],
            name="fk_portfolio_holding_port_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["security.id"],
            name="fk_portfolio_holding_sec_id",
        ),
        sa.UniqueConstraint(
            "portfolio_id",
            "as_of",
            "symbol",
            name="uq_portfolio_holding_port_date_sym",
        ),
    )
    op.create_index("ix_portfolio_holding_port_id", "portfolio_holding", ["portfolio_id"])
    op.create_index("ix_portfolio_holding_sec_id", "portfolio_holding", ["security_id"])
    op.create_index("ix_portfolio_holding_symbol", "portfolio_holding", ["symbol"])
    op.create_index("ix_portfolio_holding_as_of", "portfolio_holding", ["as_of"])
    op.create_index(
        "ix_portfolio_holding_port_date",
        "portfolio_holding",
        ["portfolio_id", "as_of"],
    )

    # 3. portfolio_risk_run
    op.create_table(
        "portfolio_risk_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("config_version", sa.String(80), nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("window_size", sa.Integer(), server_default="250", nullable=False),
        sa.Column("annualisation_factor", sa.Numeric(8, 4), server_default="252.0", nullable=False),
        sa.Column("portfolio_volatility", sa.Numeric(12, 8), nullable=False),
        sa.Column("portfolio_variance", sa.Numeric(16, 10), nullable=False),
        sa.Column("portfolio_beta", sa.Numeric(12, 8), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(12, 8), nullable=False),
        sa.Column("var_historical_95", sa.Numeric(12, 8), nullable=True),
        sa.Column("var_parametric_95", sa.Numeric(12, 8), nullable=True),
        sa.Column("es_historical_95", sa.Numeric(12, 8), nullable=True),
        sa.Column("es_parametric_95", sa.Numeric(12, 8), nullable=True),
        sa.Column("shrinkage_intensity", sa.Numeric(8, 6), nullable=False),
        sa.Column(
            "concentration_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "drawdown_series",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("status", sa.String(30), server_default="completed", nullable=False),
        sa.Column("data_sufficiency", sa.String(60), server_default="sufficient", nullable=False),
        sa.Column(
            "envelope",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolio.id"],
            name="fk_portfolio_risk_run_port_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_portfolio_risk_run_port_id", "portfolio_risk_run", ["portfolio_id"])
    op.create_index("ix_portfolio_risk_run_as_of", "portfolio_risk_run", ["as_of"])
    op.create_index("ix_portfolio_risk_run_fp", "portfolio_risk_run", ["input_fingerprint"])
    op.create_index(
        "ix_portfolio_risk_run_port_date",
        "portfolio_risk_run",
        ["portfolio_id", "as_of"],
    )

    # 4. portfolio_risk_contribution
    op.create_table(
        "portfolio_risk_contribution",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("weight", sa.Numeric(12, 8), nullable=False),
        sa.Column("asset_volatility", sa.Numeric(12, 8), nullable=False),
        sa.Column("marginal_contribution", sa.Numeric(16, 10), nullable=False),
        sa.Column("percent_contribution", sa.Numeric(12, 8), nullable=False),
        sa.Column("beta", sa.Numeric(12, 8), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["portfolio_risk_run.id"],
            name="fk_portfolio_risk_contrib_run_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["security.id"],
            name="fk_portfolio_risk_contrib_sec_id",
        ),
        sa.UniqueConstraint(
            "run_id",
            "symbol",
            name="uq_portfolio_risk_contribution_run_sym",
        ),
    )
    op.create_index("ix_portfolio_risk_contrib_run", "portfolio_risk_contribution", ["run_id"])
    op.create_index("ix_portfolio_risk_contrib_sec", "portfolio_risk_contribution", ["security_id"])
    op.create_index("ix_portfolio_risk_contrib_sym", "portfolio_risk_contribution", ["symbol"])

    # 5. analytics_artifact
    op.create_table(
        "analytics_artifact",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_type", sa.String(60), nullable=False),
        sa.Column("storage_path", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "details",
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
    )
    op.create_index("ix_analytics_artifact_run_id", "analytics_artifact", ["run_id"])
    op.create_index(
        "ix_analytics_artifact_run_type",
        "analytics_artifact",
        ["run_id", "artifact_type"],
    )


def downgrade() -> None:
    op.drop_table("analytics_artifact")
    op.drop_table("portfolio_risk_contribution")
    op.drop_table("portfolio_risk_run")
    op.drop_table("portfolio_holding")
    op.drop_table("portfolio")
