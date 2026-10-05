"""Step 8: Promoter, institutional and insider signals (dimension: governance)

Revision ID: b8c9d0e1f208
Revises: a7b8c9d0e107
Create Date: 2026-10-05 21:00:00.000000

Tables added (additive only):
  - shareholding_pattern: quarterly promoter/FII/DII/public holding % with pledge metrics
  - insider_trade: SEBI PIT Reg 7(2) and SAST Reg 29/31 disclosures

Components seeded (governance dimension, active=True):
  - gov_promoter_pledge
  - gov_promoter_holding_change
  - gov_institutional_flow
  - gov_insider_activity

Config seeded:
  - governance_analysis (version 1, approved)
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b8c9d0e1f208"
down_revision = "a7b8c9d0e107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. shareholding_pattern
    # -------------------------------------------------------------------------
    op.create_table(
        "shareholding_pattern",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SEBI Reg 31 quarter end date (e.g. 2024-12-31 for Q3 FY2025)
        sa.Column("quarter_end", sa.Date(), nullable=False),
        # Promoter group (combined: promoter + promoter group)
        sa.Column("promoter_pct", sa.Float(), nullable=True),
        # Pledged as % of total promoter holding (null if no promoter shares)
        sa.Column("promoter_pledged_pct_of_promoter", sa.Float(), nullable=True),
        # Foreign institutional investors
        sa.Column("fii_pct", sa.Float(), nullable=True),
        # Domestic institutional investors (MFs, insurance, banks)
        sa.Column("dii_pct", sa.Float(), nullable=True),
        # Retail + non-institutional public
        sa.Column("public_pct", sa.Float(), nullable=True),
        # Point-in-time: actual filing date from SEBI/exchange records
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        # Link to the source CSV / XBRL document (optional)
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_document.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Source adapter tag (CSV_IMPORT, NSE_FILING, etc.)
        sa.Column("source", sa.Text(), nullable=False, server_default="CSV_IMPORT"),
        # Deduplication key: SHA-256 of canonical content fields
        sa.Column("content_hash", sa.Text(), nullable=False),
        # Version for restatements — higher version supersedes lower for same quarter
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "security_id",
            "quarter_end",
            "version",
            name="uq_shareholding_pattern_version",
        ),
        sa.CheckConstraint(
            "(promoter_pct IS NULL OR (promoter_pct >= 0 AND promoter_pct <= 100))",
            name="ck_shareholding_promoter_pct",
        ),
        sa.CheckConstraint(
            "(fii_pct IS NULL OR (fii_pct >= 0 AND fii_pct <= 100))",
            name="ck_shareholding_fii_pct",
        ),
    )
    op.create_index(
        "ix_shareholding_pattern_security_quarter",
        "shareholding_pattern",
        ["security_id", "quarter_end", "published_at"],
    )
    op.create_index(
        "ix_shareholding_pattern_content_hash",
        "shareholding_pattern",
        ["content_hash"],
        unique=True,
    )

    # -------------------------------------------------------------------------
    # 2. insider_trade
    # -------------------------------------------------------------------------
    op.create_table(
        "insider_trade",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SEBI PIT Regulation 7(2): promoter, director, KMP, employee, etc.
        sa.Column("person_category", sa.Text(), nullable=False),
        # buy | sell | pledge | revoke_pledge
        sa.Column("txn_type", sa.Text(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=True),
        # INR value of the transaction (null if not disclosed)
        sa.Column("value", sa.Float(), nullable=True),
        # Actual transaction / execution date
        sa.Column("txn_date", sa.Date(), nullable=False),
        # When the exchange published / accepted the disclosure
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        # Link to source document (optional)
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_document.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.Text(), nullable=False, server_default="CSV_IMPORT"),
        # Deduplication key — SHA-256 of:
        # (security_id, person_category, txn_type, quantity, txn_date)
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("content_hash", name="uq_insider_trade_content_hash"),
    )
    op.create_index(
        "ix_insider_trade_security_date",
        "insider_trade",
        ["security_id", "txn_date", "published_at"],
    )
    op.create_index(
        "ix_insider_trade_published",
        "insider_trade",
        ["security_id", "published_at"],
    )

    # -------------------------------------------------------------------------
    # 3. Seed model_config for governance_analysis
    # -------------------------------------------------------------------------
    model_config_table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.Text()),
        sa.column("version", sa.String()),
        sa.column("status", sa.Text()),
        sa.column("configuration", postgresql.JSONB()),
        sa.column("configuration_hash", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    governance_config_payload = {
        # Pledge risk: level threshold and quarter-change threshold
        "pledge_level_high_threshold": 20.0,  # % of promoter shares pledged → high risk
        "pledge_change_high_threshold": 5.0,  # Δ% over 2 quarters → elevated risk
        # Holding change: 2-quarter change in promoter %
        "promoter_change_lookback_quarters": 2,
        "promoter_decline_threshold": 2.0,  # Δ% decline → elevated risk
        # Institutional flow: FII + DII combined 2-quarter change
        "institutional_flow_lookback_quarters": 2,
        "institutional_outflow_threshold": 3.0,  # Δ% decline → elevated risk
        # Insider activity window (rolling calendar days)
        "insider_window_days": 180,
        # Minimum market cap (INR) to compute insider value/mkt_cap ratio
        "min_market_cap_inr": 1_000_000_000,  # 1 billion
        # Net insider sell ratio threshold (|net_sell_value / market_cap|)
        "insider_sell_ratio_elevated": 0.002,  # 0.2% of mkt cap sold net
        # Minimum quarters required for quarter-change computation
        "min_quarters_for_change": 2,
    }

    op.bulk_insert(
        model_config_table,
        [
            {
                "id": uuid4(),
                "config_key": "governance_analysis",
                "version": "1.0.0",
                "status": "approved",
                "configuration": governance_config_payload,
                "configuration_hash": hashlib.sha256(
                    json.dumps(
                        governance_config_payload, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest(),
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        ],
    )

    # -------------------------------------------------------------------------
    # 4. Seed 4 governance component definitions (active=True)
    # -------------------------------------------------------------------------
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
            "component_id": "gov_promoter_pledge",
            "dimension": "governance",
            "name": "Promoter Pledge Risk",
            "description": (
                "Promoter shares pledged as % of promoter holding (level), "
                "plus 2-quarter change in that percentage. "
                "Higher pledge levels and rising pledge trends are riskier."
            ),
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 8",
        },
        {
            "id": uuid4(),
            "component_id": "gov_promoter_holding_change",
            "dimension": "governance",
            "name": "Promoter Holding Change",
            "description": (
                "Change in promoter group shareholding % over the last 2 reported quarters. "
                "A declining promoter stake signals reduced confidence (higher is riskier)."
            ),
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 8",
        },
        {
            "id": uuid4(),
            "component_id": "gov_institutional_flow",
            "dimension": "governance",
            "name": "Institutional Flow (FII + DII)",
            "description": (
                "Combined FII + DII holding % change over the last 2 reported quarters. "
                "Net institutional outflow (negative change) is riskier."
            ),
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 8",
        },
        {
            "id": uuid4(),
            "component_id": "gov_insider_activity",
            "dimension": "governance",
            "name": "Net Insider Selling Activity",
            "description": (
                "Net insider selling value (sells minus buys, INR) relative to market cap "
                "over a rolling config window. Higher net sell ratio is riskier."
            ),
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 8",
        },
    ]

    op.bulk_insert(component_def_table, new_components)


def downgrade() -> None:
    # Remove seeded component definitions
    op.execute(
        "DELETE FROM score_component_definition WHERE component_id IN ("
        "'gov_promoter_pledge', 'gov_promoter_holding_change', "
        "'gov_institutional_flow', 'gov_insider_activity')"
    )
    # Remove seeded model_config
    op.execute("DELETE FROM model_config WHERE config_key = 'governance_analysis' AND version = 1")
    op.drop_index("ix_insider_trade_published", table_name="insider_trade")
    op.drop_index("ix_insider_trade_security_date", table_name="insider_trade")
    op.drop_table("insider_trade")
    op.drop_index("ix_shareholding_pattern_content_hash", table_name="shareholding_pattern")
    op.drop_index("ix_shareholding_pattern_security_quarter", table_name="shareholding_pattern")
    op.drop_table("shareholding_pattern")
