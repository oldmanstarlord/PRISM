"""Step 1 model config, component registry, and risk scoring schema.

Revision ID: e1a8b9c7f201
Revises: 9c41ad7b218e
Create Date: 2026-10-04 23:59:00.000000

"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1a8b9c7f201"
down_revision: str | None = "9c41ad7b218e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _canonical_hash(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    # 1. model_config
    op.create_table(
        "model_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_key", sa.String(80), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(100), nullable=True),
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
        sa.UniqueConstraint("config_key", "version", name="uq_model_config_key_version"),
    )
    op.create_index("ix_model_config_key", "model_config", ["config_key"])
    op.create_index("ix_model_config_key_status", "model_config", ["config_key", "status"])

    # 2. score_component_definition
    op.create_table(
        "score_component_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("component_id", sa.String(80), nullable=False),
        sa.Column("dimension", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(30), nullable=False),
        sa.Column("scope", sa.String(20), server_default="universe", nullable=False),
        sa.Column("min_group_size", sa.Integer(), server_default="5", nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), server_default="1.0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("introduced_in_step", sa.String(40), nullable=False),
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
        sa.UniqueConstraint("component_id", name="uq_score_component_def_id"),
    )
    op.create_index(
        "ix_score_component_def_comp_id", "score_component_definition", ["component_id"]
    )
    op.create_index("ix_score_component_def_dimension", "score_component_definition", ["dimension"])

    # 3. score_run
    op.create_table(
        "score_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("data_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "model_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_config.id"),
            nullable=False,
        ),
        sa.Column("config_version", sa.String(40), nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("total_securities", sa.Integer(), server_default="0", nullable=False),
        sa.Column("scored_securities", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "as_of_date",
            "config_fingerprint",
            "input_fingerprint",
            name="uq_score_run_reproducible",
        ),
    )
    op.create_index("ix_score_run_as_of_date", "score_run", ["as_of_date"])
    op.create_index("ix_score_run_latest", "score_run", ["status", "as_of_date", "completed_at"])

    # 4. stock_risk_result
    op.create_table(
        "stock_risk_result",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("score_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("total_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=False),
        sa.Column("data_coverage", sa.Numeric(8, 4), nullable=False),
        sa.Column(
            "dimension_scores",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "top_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "limitations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "security_id", name="uq_stock_risk_result_run_security"),
    )
    op.create_index("ix_stock_risk_result_run_id", "stock_risk_result", ["run_id"])
    op.create_index("ix_stock_risk_result_security_id", "stock_risk_result", ["security_id"])
    op.create_index("ix_stock_risk_result_symbol", "stock_risk_result", ["symbol"])
    op.create_index("ix_stock_risk_result_ranking", "stock_risk_result", ["run_id", "total_score"])

    # 5. score_component_value
    op.create_table(
        "score_component_value",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("score_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id"),
            nullable=False,
        ),
        sa.Column("component_id", sa.String(80), nullable=False),
        sa.Column("raw_value", sa.Numeric(24, 8), nullable=True),
        sa.Column("percentile_rank", sa.Numeric(8, 4), nullable=True),
        sa.Column("points", sa.Numeric(8, 4), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("data_as_of", sa.Date(), nullable=True),
        sa.Column("data_age_days", sa.Integer(), nullable=True),
        sa.Column(
            "evidence_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.UniqueConstraint("run_id", "security_id", "component_id", name="uq_score_component_val"),
    )
    op.create_index("ix_score_component_val_run_id", "score_component_value", ["run_id"])
    op.create_index("ix_score_component_val_security_id", "score_component_value", ["security_id"])
    op.create_index(
        "ix_score_component_val_component_id", "score_component_value", ["component_id"]
    )
    op.create_index("ix_score_component_val_status", "score_component_value", ["status"])

    # 6. confidence_factor_value
    op.create_table(
        "confidence_factor_value",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("score_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id"),
            nullable=False,
        ),
        sa.Column("factor_name", sa.String(40), nullable=False),
        sa.Column("factor_value", sa.Numeric(8, 4), nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), nullable=False),
        sa.Column("cap_applied", sa.String(80), nullable=True),
        sa.UniqueConstraint(
            "run_id", "security_id", "factor_name", name="uq_confidence_factor_val"
        ),
    )
    op.create_index("ix_confidence_factor_val_run_id", "confidence_factor_value", ["run_id"])
    op.create_index(
        "ix_confidence_factor_val_security_id", "confidence_factor_value", ["security_id"]
    )

    # 7. audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "inputs_ref",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_subject", "audit_log", ["subject"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_log_run_id", "audit_log", ["run_id"])

    # --- Seed data: model_config (status = 'draft') ---
    model_config_table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.String),
        sa.column("version", sa.String),
        sa.column("status", sa.String),
        sa.column("configuration", sa.Text),
        sa.column("configuration_hash", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(UTC)

    portfolio_rules = {
        "input_modes": ["quantity", "target_weight"],
        "cash_symbol": "CASH",
        "cash_currency": "INR",
        "weight_normalization": "strict_sum_to_one",
        "valuation_price": "adjusted_close",
        "return_type": "log_return",
        "annualisation_factor": 252,
        "default_lookback_days": 250,
        "rebalancing": "buy_and_hold",
        "benchmark": "NIFTY 200",
        "max_stale_days": 5,
        "risk_free_rate_source": "GOI_91D_TBILL",
    }

    risk_score_weights = {
        "dimensions": {
            "market": 25,
            "fundamentals": 20,
            "liquidity": 10,
            "structure": 10,
            "relative": 10,
            "governance": 10,
            "events": 10,
            "macro": 5,
        },
        "default_component_weight": 1.0,
        "min_industry_group_size": 5,
        "min_coverage_ratio": 0.70,
        "tie_rule": "weak_percentile",
    }

    confidence_factors = {
        "factor_weights": {
            "data_coverage": 1.0,
            "data_freshness": 1.0,
            "source_agreement": 1.0,
            "signal_agreement": 1.0,
            "model_stability": 1.0,
            "evidence_volume": 1.0,
        },
        "caps": {
            "stale_price_cap": 50.0,
            "stale_price_days": 5,
            "low_coverage_cap": 60.0,
            "low_coverage_threshold": 0.70,
        },
        "max_age_days": {
            "market": 5,
            "liquidity": 5,
            "fundamentals": 120,
            "governance": 365,
            "events": 30,
            "macro": 30,
        },
    }

    op.bulk_insert(
        model_config_table,
        [
            {
                "id": uuid4(),
                "config_key": "portfolio_rules",
                "version": "v1",
                "status": "draft",
                "configuration": json.dumps(portfolio_rules),
                "configuration_hash": _canonical_hash(portfolio_rules),
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid4(),
                "config_key": "risk_score_weights",
                "version": "v1",
                "status": "draft",
                "configuration": json.dumps(risk_score_weights),
                "configuration_hash": _canonical_hash(risk_score_weights),
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid4(),
                "config_key": "confidence_factors",
                "version": "v1",
                "status": "draft",
                "configuration": json.dumps(confidence_factors),
                "configuration_hash": _canonical_hash(confidence_factors),
                "created_at": now,
                "updated_at": now,
            },
        ],
    )

    # --- Seed data: score_component_definition ---
    component_def_table = sa.table(
        "score_component_definition",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("component_id", sa.String),
        sa.column("dimension", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("direction", sa.String),
        sa.column("scope", sa.String),
        sa.column("min_group_size", sa.Integer),
        sa.column("weight", sa.Numeric),
        sa.column("active", sa.Boolean),
        sa.column("introduced_in_step", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    seed_components = [
        # Price-side planned for Step 5 (active=False)
        {
            "id": uuid4(),
            "component_id": "volatility_60d",
            "dimension": "market",
            "name": "60-Day Realised Volatility",
            "description": "Annualised standard deviation of trailing 60 trading day log returns.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "max_drawdown_250d",
            "dimension": "market",
            "name": "250-Day Maximum Drawdown",
            "description": "Peak-to-trough decline over the trailing 250 trading day window.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "downside_deviation_60d",
            "dimension": "market",
            "name": "60-Day Downside Semi-Deviation",
            "description": "Standard deviation of negative daily returns below zero over 60 days.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "amihud_illiquidity_60d",
            "dimension": "liquidity",
            "name": "60-Day Amihud Illiquidity Ratio",
            "description": "Average ratio of absolute daily return to daily rupee volume.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "turnover_ratio_60d",
            "dimension": "liquidity",
            "name": "60-Day Turnover Ratio",
            "description": "Average daily trading volume relative to shares outstanding.",
            "direction": "lower_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "mst_degree_centrality",
            "dimension": "structure",
            "name": "MST Degree Centrality",
            "description": "Incident edges count in the approved Layer 2 Minimum Spanning Tree.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "sector_divergence_residual_20d",
            "dimension": "relative",
            "name": "20-Day Sector Divergence Residual",
            "description": "Standardized residual from Layer 1 sector-divergence-v1 trailing OLS.",
            "direction": "higher_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        # Fundamental, governance, event, macro placeholders
        {
            "id": uuid4(),
            "component_id": "debt_to_equity",
            "dimension": "fundamentals",
            "name": "Debt to Equity Ratio",
            "description": "Total debt divided by total shareholder equity from latest filing.",
            "direction": "higher_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 2",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "interest_coverage",
            "dimension": "fundamentals",
            "name": "Interest Coverage Ratio",
            "description": "EBIT divided by interest expenses from trailing 12-month statements.",
            "direction": "lower_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 2",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "promoter_pledging_pct",
            "dimension": "governance",
            "name": "Promoter Pledged Shares Percentage",
            "description": "Percentage of promoter shareholding that is pledged.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 2",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "filing_sentiment_negative",
            "dimension": "events",
            "name": "Negative Filing Sentiment Probability",
            "description": "FinBERT negative sentiment probability on latest exchange filings.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 2",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "macro_rate_sensitivity",
            "dimension": "macro",
            "name": "Interest Rate Beta",
            "description": "Sensitivity of stock returns to 10-year benchmark yield changes.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": False,
            "introduced_in_step": "Step 3",
            "created_at": now,
            "updated_at": now,
        },
    ]

    op.bulk_insert(component_def_table, seed_components)


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("confidence_factor_value")
    op.drop_table("score_component_value")
    op.drop_table("stock_risk_result")
    op.drop_table("score_run")
    op.drop_table("score_component_definition")
    op.drop_table("model_config")
