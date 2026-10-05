"""Step 5: Score components activation and risk engine parameters seed.

Revision ID: e5f6a7b8c905
Revises: d4e5f6a7b804
Create Date: 2026-10-05 01:25:00.000000
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c905"
down_revision: str | None = "d4e5f6a7b804"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.now(UTC)

    # 1. Seed or activate price-side components in score_component_definition
    components_table = sa.table(
        "score_component_definition",
        sa.column("id", sa.Uuid()),
        sa.column("component_id", sa.String()),
        sa.column("dimension", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("direction", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("min_group_size", sa.Integer()),
        sa.column("weight", sa.Numeric()),
        sa.column("active", sa.Boolean()),
        sa.column("introduced_in_step", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    step_5_components = [
        {
            "id": uuid4(),
            "component_id": "ewma_volatility",
            "dimension": "market",
            "name": "EWMA Realised Volatility",
            "description": "Annualised EWMA return volatility with decay factor (lambda=0.94).",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "beta_to_benchmark",
            "dimension": "market",
            "name": "Benchmark Beta",
            "description": "Rolling 250-day OLS market beta relative to NIFTY 200 benchmark index.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "max_drawdown_1y",
            "dimension": "market",
            "name": "1-Year Maximum Drawdown",
            "description": "Peak-to-trough decline over trailing 250 trading days.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "tail_loss",
            "dimension": "market",
            "name": "Historical Tail Loss (Expected Shortfall)",
            "description": "Historical Expected Shortfall at 95% confidence over 250 days.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "avg_traded_value",
            "dimension": "liquidity",
            "name": "20-Day Average Daily Traded Value",
            "description": "Rolling 20-day mean of daily rupee traded value (lower is riskier).",
            "direction": "lower_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "zero_volume_days",
            "dimension": "liquidity",
            "name": "Zero Volume Days",
            "description": "Count of non-trading/zero-volume days over trailing 60 trading days.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "mst_centrality",
            "dimension": "structure",
            "name": "MST Graph Centrality",
            "description": "Weighted incident correlation centrality in approved correlation MST.",
            "direction": "higher_is_riskier",
            "scope": "universe",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": uuid4(),
            "component_id": "sector_divergence",
            "dimension": "relative",
            "name": "20-Day Sector Divergence",
            "description": "Absolute 20-day residual divergence score from Layer 1.",
            "direction": "higher_is_riskier",
            "scope": "industry",
            "min_group_size": 5,
            "weight": 1.0,
            "active": True,
            "introduced_in_step": "Step 5",
            "created_at": now,
            "updated_at": now,
        },
    ]

    op.bulk_insert(components_table, step_5_components)

    # 2. Seed risk_engine_parameters in model_config
    params_payload = {
        "ewma_lambda": 0.94,
        "volatility_annualisation_factor": 252,
        "beta_lookback_days": 250,
        "drawdown_lookback_days": 250,
        "tail_loss_lookback_days": 250,
        "tail_loss_alpha": 0.05,
        "adv_lookback_days": 20,
        "zero_volume_lookback_days": 60,
        "sector_divergence_horizon": 20,
        "min_coverage_ratio": 0.70,
        "min_industry_group_size": 5,
        "tie_rule": "weak_percentile",
        "reason_templates": {
            "higher_is_riskier": (
                "{component_name} is in the {percentile:.0f}th percentile ({raw_value:.2f}), "
                "contributing +{contribution:.1f} pts to {dimension} risk."
            ),
            "lower_is_riskier": (
                "{component_name} is depressed at the {percentile:.0f}th percentile "
                "({raw_value:.2f}), adding +{contribution:.1f} pts to {dimension} risk."
            ),
        },
    }
    serialized_cfg = json.dumps(params_payload, sort_keys=True, separators=(",", ":"))
    cfg_hash = hashlib.sha256(serialized_cfg.encode("utf-8")).hexdigest()

    model_config_table = sa.table(
        "model_config",
        sa.column("id", sa.Uuid()),
        sa.column("config_key", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", sa.Text()),
        sa.column("configuration_hash", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        model_config_table,
        [
            {
                "id": uuid4(),
                "config_key": "risk_engine_parameters",
                "version": "1.0.0",
                "status": "approved",
                "configuration": serialized_cfg,
                "configuration_hash": cfg_hash,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM score_component_definition WHERE component_id IN ("
            "'ewma_volatility', 'beta_to_benchmark', 'max_drawdown_1y', 'tail_loss', "
            "'avg_traded_value', 'zero_volume_days', 'mst_centrality', 'sector_divergence')"
        )
    )
    op.execute(sa.text("DELETE FROM model_config WHERE config_key = 'risk_engine_parameters'"))
