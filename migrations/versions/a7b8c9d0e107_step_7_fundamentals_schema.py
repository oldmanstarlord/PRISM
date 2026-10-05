"""Step 7: Fundamentals as score components (dimension: fundamentals)

Revision ID: a7b8c9d0e107
Revises: f6a7b8c9d006
Create Date: 2026-10-05 20:00:00.000000
"""

from __future__ import annotations

import json
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e107"
down_revision = "f6a7b8c9d006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. source_document table
    op.create_table(
        "source_document",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),  # YAHOO_FUNDAMENTALS, CSV_IMPORT, etc.
        sa.Column("source_doc_id", sa.Text(), nullable=True),
        sa.Column("doc_type", sa.Text(), nullable=False),  # quarterly_results, annual_report
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "published_at_method", sa.Text(), nullable=False, server_default="actual"
        ),  # actual | estimated
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("raw_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_source_document_security_published",
        "source_document",
        ["security_id", "published_at"],
    )

    # 2. fundamental_period table
    op.create_table(
        "fundamental_period",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_type", sa.Text(), nullable=False),  # quarter | year
        sa.Column("basis", sa.Text(), nullable=False),  # consolidated | standalone | unknown
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "published_at_method", sa.Text(), nullable=False, server_default="actual"
        ),  # actual | estimated
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_document.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revenue", sa.Float(), nullable=True),
        sa.Column("operating_profit", sa.Float(), nullable=True),
        sa.Column("pat", sa.Float(), nullable=True),
        sa.Column("interest_expense", sa.Float(), nullable=True),
        sa.Column("total_debt", sa.Float(), nullable=True),
        sa.Column("total_equity", sa.Float(), nullable=True),
        sa.Column("total_assets", sa.Float(), nullable=True),
        sa.Column("cash_from_operations", sa.Float(), nullable=True),
        sa.Column(
            "extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),  # Bank/NBFC items: npa, car, etc.
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "security_id",
            "period_end",
            "period_type",
            "basis",
            "version",
            name="uq_fundamental_period_version",
        ),
    )
    op.create_index(
        "ix_fundamental_period_sec_end_pub",
        "fundamental_period",
        ["security_id", "period_end", "published_at"],
    )

    # 3. fundamental_metric table
    op.create_table(
        "fundamental_metric",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("metric_key", sa.Text(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("source_period_end", sa.Date(), nullable=True),
        sa.Column("data_age_days", sa.Integer(), nullable=True),
        sa.Column("peer_group", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default="computed"
        ),  # computed | missing | insufficient | flagged
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "security_id",
            "as_of",
            "metric_key",
            "peer_group",
            name="uq_fundamental_metric_sec_asof_key",
        ),
    )
    op.create_index(
        "ix_fundamental_metric_asof_peer",
        "fundamental_metric",
        ["as_of", "metric_key", "peer_group"],
    )

    # 4. Seed model_config for fundamental_analysis
    model_config_table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.Text()),
        sa.column("version", sa.Integer()),
        sa.column("status", sa.Text()),
        sa.column("configuration", sa.Text()),
        sa.column("checksum", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("created_by", sa.Text()),
    )

    fundamental_config_payload = {
        "quarterly_reporting_lag_days": 45,
        "annual_reporting_lag_days": 60,
        "min_peer_group_size": 5,
        "ttm_min_quarters_for_yoy": 5,
        "financial_sectors": [
            "Financial Services",
            "Banks",
            "Banking",
            "Finance",
            "NBFC",
        ],
        "default_basis_preference": "consolidated",
        "quality_rules": {
            "flag_negative_equity": True,
            "flag_extreme_margin_pct": 500.0,
            "min_asset_value": 0.0,
        },
    }

    op.bulk_insert(
        model_config_table,
        [
            {
                "id": uuid4(),
                "config_key": "fundamental_analysis",
                "version": 1,
                "status": "approved",
                "configuration": json.dumps(fundamental_config_payload, sort_keys=True),
                "checksum": "step7_fundamentals_v1",
                "description": (
                    "Fundamental analysis configuration: reporting lags, "
                    "peer group profiles, and validation rules."
                ),
                "created_by": "step7_migration",
            },
        ],
    )

    # 5. Seed / activate the 4 fundamental components in score_component_definition
    component_def_table = sa.table(
        "score_component_definition",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("component_id", sa.Text()),
        sa.column("dimension", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("direction", sa.Text()),
        sa.column("scope", sa.Text()),
        sa.column("min_group_size", sa.Integer()),
        sa.column("weight", sa.Float()),
        sa.column("active", sa.Boolean()),
        sa.column("introduced_in_step", sa.Text()),
    )

    new_components = [
        {
            "id": uuid4(),
            "component_id": "fund_leverage",
            "dimension": "fundamentals",
            "name": "Financial Leverage",
            "description": (
                "Total Debt to Total Equity (or Assets to Equity for banks) "
                "relative to industry peers (higher is riskier)."
            ),
            "direction": "higher_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 7",
        },
        {
            "id": uuid4(),
            "component_id": "fund_coverage",
            "dimension": "fundamentals",
            "name": "Solvency & Interest Coverage",
            "description": (
                "Operating profit to interest expense coverage ratio (lower is riskier)."
            ),
            "direction": "lower_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 7",
        },
        {
            "id": uuid4(),
            "component_id": "fund_profit_trend",
            "dimension": "fundamentals",
            "name": "TTM Profit Growth Trend",
            "description": (
                "Trailing 12-month net profit YoY growth rate relative to "
                "industry peers (lower is riskier)."
            ),
            "direction": "lower_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 7",
        },
        {
            "id": uuid4(),
            "component_id": "fund_cashflow_quality",
            "dimension": "fundamentals",
            "name": "Cash Flow Quality (CFO / PAT)",
            "description": (
                "Operating cash flow to net profit ratio over trailing 12 months "
                "(lower is riskier)."
            ),
            "direction": "lower_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 7",
        },
    ]

    op.bulk_insert(component_def_table, new_components)


def downgrade() -> None:
    # Remove seeded score_component_definitions
    op.execute(
        "DELETE FROM score_component_definition WHERE component_id IN ("
        "'fund_leverage', 'fund_coverage', 'fund_profit_trend', 'fund_cashflow_quality')"
    )
    # Remove seeded model_config
    op.execute("DELETE FROM model_config WHERE config_key = 'fundamental_analysis' AND version = 1")
    op.drop_table("fundamental_metric")
    op.drop_table("fundamental_period")
    op.drop_table("source_document")
