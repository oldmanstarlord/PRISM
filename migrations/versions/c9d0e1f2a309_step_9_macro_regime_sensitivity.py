"""Step 9: Macro series, rule-based market regime, and sector sensitivity (dimension: macro)

Revision ID: c9d0e1f2a309
Revises: b8c9d0e1f208
Create Date: 2026-10-05 22:15:00.000000

Tables added (additive only):
  - macro_series_definition: series catalog (crude_oil, usd_inr, in_10y_yield, etc.)
  - macro_observation: point-in-time observations with published_at and versioning
  - market_regime: rule-based market regime state (calm, trending, stressed)
  - sector_macro_sensitivity: rolling point-in-time industry regression sensitivities

Config seeded:
  - macro_regime_sensitivity (version 1.0.0, approved)

Components seeded:
  - macro_exposure (dimension: macro, active=True)
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
revision = "c9d0e1f2a309"
down_revision = "b8c9d0e1f208"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. macro_series_definition
    # -------------------------------------------------------------------------
    op.create_table(
        "macro_series_definition",
        sa.Column("series_key", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="DAILY"),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # -------------------------------------------------------------------------
    # 2. macro_observation
    # -------------------------------------------------------------------------
    op.create_table(
        "macro_observation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "series_key",
            sa.String(50),
            sa.ForeignKey("macro_series_definition.series_key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "series_key", "obs_date", "version", name="uq_macro_observation_version"
        ),
    )
    op.create_index(
        "ix_macro_obs_query",
        "macro_observation",
        ["series_key", "obs_date", "published_at"],
    )

    # -------------------------------------------------------------------------
    # 3. market_regime
    # -------------------------------------------------------------------------
    op.create_table(
        "market_regime",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config_version", sa.String(40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("as_of", "config_version", name="uq_market_regime_as_of_version"),
    )
    op.create_index("ix_market_regime_as_of", "market_regime", ["as_of"])

    # -------------------------------------------------------------------------
    # 4. sector_macro_sensitivity
    # -------------------------------------------------------------------------
    op.create_table(
        "sector_macro_sensitivity",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("industry", sa.String(160), nullable=False),
        sa.Column(
            "series_key",
            sa.String(50),
            sa.ForeignKey("macro_series_definition.series_key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("beta", sa.Float(), nullable=False),
        sa.Column("t_stat", sa.Float(), nullable=False),
        sa.Column("n_obs", sa.Integer(), nullable=False),
        sa.Column("p_value", sa.Float(), nullable=False),
        sa.Column("is_significant", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("config_version", sa.String(40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "industry",
            "series_key",
            "window_end",
            "config_version",
            name="uq_sector_macro_sensitivity",
        ),
    )
    op.create_index(
        "ix_sector_macro_lookup",
        "sector_macro_sensitivity",
        ["industry", "series_key", "window_end"],
    )

    # -------------------------------------------------------------------------
    # 5. Seed 5 macro series definitions
    # -------------------------------------------------------------------------
    macro_series_def_table = sa.table(
        "macro_series_definition",
        sa.column("series_key", sa.String(50)),
        sa.column("name", sa.String(255)),
        sa.column("source", sa.String(120)),
        sa.column("frequency", sa.String(20)),
        sa.column("unit", sa.String(50)),
        sa.column("license_note", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(UTC)
    series_definitions = [
        {
            "series_key": "crude_oil",
            "name": "Brent Crude Oil Continuous",
            "source": "YAHOO_BRENT",
            "frequency": "DAILY",
            "unit": "USD/bbl",
            "license_note": "Yahoo Finance (BZ=F) / EIA adapter for academic & evaluation research",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "series_key": "usd_inr",
            "name": "USD / INR Reference Exchange Rate",
            "source": "FBIL_YAHOO",
            "frequency": "DAILY",
            "unit": "INR",
            "license_note": "FBIL reference rates / Yahoo Finance (INR=X) public market data",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "series_key": "in_10y_yield",
            "name": "India 10-Year Benchmark G-Sec Yield",
            "source": "CCIL_RBI",
            "frequency": "DAILY",
            "unit": "%",
            "license_note": "CCIL and RBI public statistical releases on sovereign yields",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "series_key": "india_vix",
            "name": "NSE India Volatility Index (India VIX)",
            "source": "NSE_INDIA",
            "frequency": "DAILY",
            "unit": "index_points",
            "license_note": "NSE India public index data (^INDIAVIX)",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "series_key": "fii_dii_net_flows",
            "name": "FII & DII Cash Market Net Investment",
            "source": "NSE_BSE_NSDL",
            "frequency": "DAILY",
            "unit": "INR_crores",
            "license_note": "Stock exchange and depository regulatory daily turnover reports",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]

    op.bulk_insert(macro_series_def_table, series_definitions)

    # -------------------------------------------------------------------------
    # 6. Seed model_config: macro_regime_sensitivity v1.0.0
    # -------------------------------------------------------------------------
    model_config_table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.Text()),
        sa.column("version", sa.Text()),
        sa.column("status", sa.Text()),
        sa.column("configuration", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("configuration_hash", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    macro_config_payload = {
        "rv_lookback_days": 21,
        "rv_history_days": 252,
        "correlation_lookback_days": 63,
        "correlation_history_days": 252,
        "vix_calm_threshold": 14.5,
        "vix_trending_threshold": 16.5,
        "vix_stressed_threshold": 22.0,
        "vix_exit_stressed_threshold": 19.0,
        "vol_pctl_calm_entry": 40.0,
        "vol_pctl_trending_entry": 45.0,
        "vol_pctl_stressed_entry": 75.0,
        "vol_pctl_exit_calm": 35.0,
        "vol_pctl_exit_stressed": 65.0,
        "corr_pctl_calm_entry": 40.0,
        "corr_pctl_trending_entry": 45.0,
        "corr_pctl_stressed_entry": 75.0,
        "corr_pctl_exit_calm": 35.0,
        "corr_pctl_exit_stressed": 65.0,
        "sensitivity_lookback_days": 63,
        "min_sensitivity_observations": 30,
        "t_stat_significance_threshold": 1.96,
        "recent_move_window_days": 5,
        "recent_move_baseline_days": 63,
        "regime_multipliers": {
            "calm": 1.0,
            "trending": 1.25,
            "stressed": 1.5,
        },
    }

    cfg_json = json.dumps(macro_config_payload, sort_keys=True, separators=(",", ": "))
    cfg_hash = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()

    ctx = op.get_context()
    if getattr(ctx, "as_sql", False):
        insert_sql = (
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, "
            "configuration_hash, created_at, updated_at) "
            f"VALUES ('{uuid4()}', 'macro_regime_sensitivity', '1.0.0', 'approved', "
            f"'{cfg_json}'::jsonb, '{cfg_hash}', now(), now())"
        )
        op.execute(insert_sql)
    else:
        op.bulk_insert(
            model_config_table,
            [
                {
                    "id": uuid4(),
                    "config_key": "macro_regime_sensitivity",
                    "version": "1.0.0",
                    "status": "approved",
                    "configuration": macro_config_payload,
                    "configuration_hash": cfg_hash,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )

    # -------------------------------------------------------------------------
    # 7. Seed score_component_definition: macro_exposure (active=True)
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

    op.bulk_insert(
        component_def_table,
        [
            {
                "id": uuid4(),
                "component_id": "macro_exposure",
                "dimension": "macro",
                "name": "Macroeconomic Regime & Sector Sensitivity",
                "description": (
                    "Evaluates stock vulnerability to macro shocks "
                    "(Crude, FX, Rates, Volatility, Flows) "
                    "transmitted through sector sensitivities, scaled by market regime state."
                ),
                "direction": "higher_is_riskier",
                "scope": "universe",
                "min_group_size": 5,
                "weight": 1.0,
                "active": True,
                "introduced_in_step": "Step 9",
            }
        ],
    )


def downgrade() -> None:
    # Additive migration policy: downgrade leaves tables intact or drops Step 9 additive tables
    op.drop_table("sector_macro_sensitivity")
    op.drop_table("market_regime")
    op.drop_table("macro_observation")
    op.drop_table("macro_series_definition")
