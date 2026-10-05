"""Seed the complete Step 12 risk configuration as a non-default draft.

Revision ID: a3b4c5d6e712
Revises: f2a3b4c5d612
Create Date: 2026-10-06 01:30:00.000000

"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3b4c5d6e712"
down_revision = "f2a3b4c5d612"
branch_labels = None
depends_on = None


RISK_CONFIG_V2: dict[str, object] = {
    "ewma_lambda": 0.94,
    "volatility_annualisation_factor": 252,
    "ewma_lookback_days": 180,
    "beta_lookback_days": 250,
    "benchmark_id": "NIFTY_200",
    "drawdown_lookback_days": 250,
    "tail_loss_lookback_days": 250,
    "tail_loss_alpha": 0.05,
    "adv_lookback_days": 20,
    "zero_volume_lookback_days": 60,
    "minimum_observations": {
        "ewma_volatility": 20,
        "beta_to_benchmark": 30,
        "max_drawdown_1y": 30,
        "tail_loss": 20,
        "avg_traded_value": 5,
        "zero_volume_days": 5,
    },
    "sector_divergence_horizon": 20,
    "sector_divergence_max_age_days": 5,
    "mst_max_age_days": 35,
    "dimension_weights": {
        "market": 25.0,
        "fundamentals": 20.0,
        "liquidity": 10.0,
        "structure": 10.0,
        "relative": 10.0,
        "governance": 10.0,
        "events": 10.0,
        "macro": 5.0,
    },
    "component_weights": {
        "ewma_volatility": 1.0,
        "beta_to_benchmark": 1.0,
        "max_drawdown_1y": 1.0,
        "tail_loss": 1.0,
        "avg_traded_value": 1.0,
        "zero_volume_days": 1.0,
        "mst_centrality": 1.0,
        "sector_divergence": 1.0,
        "fund_leverage": 1.0,
        "fund_coverage": 1.0,
        "fund_profit_trend": 1.0,
        "fund_cashflow_quality": 1.0,
        "gov_promoter_pledge": 1.0,
        "gov_promoter_holding_change": 1.0,
        "gov_institutional_flow": 1.0,
        "gov_insider_activity": 1.0,
        "event_risk_pressure": 1.0,
        "macro_exposure": 1.0,
        "news_policy_pressure": 1.0,
    },
    "decay_half_lives_days": {
        "event_risk_pressure": 14.0,
        "news_policy_pressure": 14.0,
    },
    "event_risk_pressure": {
        "recency_half_life_days": 14.0,
        "lookback_days": 90,
        "positive_offset_cap": 0.30,
    },
    "news_policy_pressure": {
        "recency_half_life_days": 14.0,
        "lookback_days": 90,
        "tailwind_mitigation_cap": 0.30,
    },
    "fundamental_analysis": {
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
    },
    "governance_analysis": {
        "pledge_level_high_threshold": 20.0,
        "pledge_change_high_threshold": 5.0,
        "promoter_change_lookback_quarters": 2,
        "promoter_decline_threshold": 2.0,
        "institutional_flow_lookback_quarters": 2,
        "institutional_outflow_threshold": 3.0,
        "insider_window_days": 180,
        "min_market_cap_inr": 1000000000.0,
        "insider_sell_ratio_elevated": 0.002,
        "min_quarters_for_change": 2,
    },
    "regime_multipliers": {"calm": 1.0, "trending": 1.25, "stressed": 1.5},
    "recent_move_window_days": 5,
    "recent_move_baseline_days": 63,
    "min_coverage_ratio": 0.70,
    "coverage_required_observations": {
        "ewma_volatility": 60,
        "beta_to_benchmark": 250,
        "max_drawdown_1y": 250,
        "tail_loss": 250,
        "avg_traded_value": 20,
        "zero_volume_days": 60,
    },
    "min_industry_group_size": 5,
    "stale_price_days_cap_threshold": 5,
    "stale_price_cap": 50.0,
    "low_coverage_cap": 60.0,
    "confidence_factor_weights": {
        "data_coverage": 1.0,
        "data_freshness": 1.0,
        "source_agreement": 1.0,
        "signal_agreement": 1.0,
        "model_stability": 1.0,
        "evidence_volume": 1.0,
    },
    "confidence_max_age_days": {
        "market": 5,
        "liquidity": 5,
        "structure": 35,
        "relative": 5,
        "fundamentals": 120,
        "governance": 365,
        "events": 30,
        "macro": 30,
    },
    "evidence_volume_scale": 5.0,
    "source_agreement_lookback_days": 60,
    "volatility_target_observations": 60,
    "portfolio_score_weights": {"holding_risk": 0.80, "structure": 0.20},
    "portfolio_structure_weights": {"cluster_concentration": 0.50, "effective_bets": 0.50},
    "large_holding_weight_threshold": 0.10,
    "ablation": {"excluded_components": [], "excluded_dimensions": []},
    "tie_rule": "weak_percentile",
    "reason_templates": {
        "higher_is_riskier": (
            "{component_name} is elevated at the {percentile:.0f}th percentile "
            "({raw_value:.2f}), contributing +{contribution:.1f} pts to {dimension} risk."
        ),
        "lower_is_riskier": (
            "{component_name} is depressed at the {percentile:.0f}th percentile "
            "({raw_value:.2f}), adding +{contribution:.1f} pts to {dimension} risk."
        ),
    },
    "approval_note": "Draft only; owner approval required before this version becomes default.",
}


def upgrade() -> None:
    payload = json.dumps(RISK_CONFIG_V2, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("configuration_hash", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    context = op.get_context()
    if getattr(context, "as_sql", False):
        # Escape colons so SQLAlchemy TextClause does not parse JSON numeric values
        # (for example ``:20``) as offline bind parameters.
        escaped = payload.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{uuid4()}', 'risk_engine_parameters', '2.0.0', 'draft', "
            f"'{escaped}'::jsonb, '{fingerprint}', now(), now())"
        )
    else:
        op.bulk_insert(
            table,
            [
                {
                    "id": uuid4(),
                    "config_key": "risk_engine_parameters",
                    "version": "2.0.0",
                    "status": "draft",
                    "configuration": RISK_CONFIG_V2,
                    "configuration_hash": fingerprint,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_config "
        "WHERE config_key = 'risk_engine_parameters' AND version = '2.0.0' AND status = 'draft'"
    )
