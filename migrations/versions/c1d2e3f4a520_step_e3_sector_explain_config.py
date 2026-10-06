"""Seed draft sector-divergence explanation rules.

Revision ID: c1d2e3f4a520
Revises: b0c1d2e3f419
Create Date: 2026-10-06
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a520"
down_revision = "b0c1d2e3f419"
branch_labels = None
depends_on = None

CONFIG: dict[str, object] = {
    "approval_note": "Draft Step E3 thresholds and wording; owner review is required.",
    "windows": [1, 5, 20, 60],
    "primary_horizon": 20,
    "minimum_contemporaneous_peers": 4,
    "persistence_window": 20,
    "flag_threshold_abs_z": 1.0,
    "trend_thresholds_percent": {"1": 0.25, "5": 0.75, "20": 1.5, "60": 3.0},
    "risk_rules": {
        "fundamentals_percentile_min": 75.0,
        "volatility_percentile_min": 75.0,
        "negative_direction_only": True,
    },
    "event_lookback_days": 60,
    "max_chart_points": 100,
    "banned_phrases": [
        "because",
        "buy",
        "sell",
        "hold",
        "price target",
        "will rise",
        "will fall",
        "guaranteed",
        "caused by",
    ],
    "correlation_required_phrase": "moves together with",
    "disclaimer": (
        "PRISM provides descriptive risk explanations, not investment advice or price predictions."
    ),
    "limitations": [
        "A divergence alone is not a risk verdict; it shows the stock is behaving "
        "differently from its peers.",
        "The peer benchmark is a leave-one-out statistical series, not a tradeable industry index.",
        "Bands describe historical standardized residuals and are not probability or "
        "prediction claims.",
        "Daily adjusted closing prices are not real-time prices.",
    ],
    "band_wording": {
        "normal": "within its normal historical residual band",
        "moderate": "moderately outside its historical residual band",
        "strong": "strongly outside its historical residual band",
        "extreme": "extremely outside its historical residual band",
    },
    "direction_wording": {
        "outperforming": "outperforming its peer model",
        "underperforming": "underperforming its peer model",
    },
    "templates": {
        "stock_headline": "{symbol} is {direction} its {industry} peer model over 20 trading days",
        "sector_trend": (
            "The leave-one-out peer median returned {sector_return_20}% over 20 trading days, "
            "labelled {sector_trend}; {breadth}% of peers had positive 20-day returns."
        ),
        "sector_dispersion": (
            "Peer 20-day return dispersion was {dispersion}% across {peer_count} eligible peers."
        ),
        "stock_trend": (
            "{symbol} returned {stock_return_20}% over 20 trading days, labelled {stock_trend}."
        ),
        "expected": (
            "The stored regression expected a one-day return of {expected_return}% from alpha "
            "and beta; the observed residual was {residual_1}% and R-squared was {r_squared}%."
        ),
        "flagged": (
            "The stored 20-day standardized residual was {z_20}, {band_text} and {direction_text}."
        ),
        "unusual": (
            "Its absolute 20-day score ranked at the {history_percentile} percentile of its "
            "available history and the {peer_percentile} percentile among industry peers today."
        ),
        "persistence": (
            "The absolute 20-day score exceeded 1 on {persistence_count} of the last "
            "{persistence_observations} available run dates."
        ),
        "divergence_not_verdict": (
            "A divergence alone is not a risk verdict; it shows the stock is behaving "
            "differently from its peers."
        ),
        "risk_supported": (
            "The negative divergence coincides with {supporting_signal}; this supports a "
            "descriptive risk reading, not a prediction."
        ),
        "contribution": (
            "The sector-divergence component was at percentile {component_percentile}, with "
            "{component_points} points and weight {component_weight}; its configured share of "
            "the total risk score was {contribution_share}%."
        ),
        "coincident": (
            "There were {coincident_count} stored company events, linked news items, or "
            "fundamental publications inside the configured window."
        ),
        "sector_headline": "Stored trend and divergence evidence for {industry}",
        "sector_overview": (
            "The industry median returned {sector_return_20}% over 20 trading days, labelled "
            "{sector_trend}, with {breadth}% positive breadth and {dispersion}% dispersion."
        ),
        "sector_flagged": (
            "{flagged_count} of {stock_count} scored stocks had an absolute 20-day residual "
            "score of at least {flag_threshold}."
        ),
        "sector_macro": (
            "The strongest significant stored macro sensitivities were {macro_drivers}."
        ),
        "sector_news": (
            "The configured window contained {news_count} stored industry-linked news or "
            "event items."
        ),
        "sector_divergers": "The largest absolute stored divergences were {top_divergers}.",
    },
}


def upgrade() -> None:
    table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", postgresql.JSONB()),
        sa.column("configuration_hash", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    canonical = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    now = datetime.now(UTC)
    row = {
        "id": uuid4(),
        "config_key": "explain_sector_rules",
        "version": "1.0.0",
        "status": "draft",
        "configuration": CONFIG,
        "configuration_hash": hashlib.sha256(canonical.encode()).hexdigest(),
        "created_at": now,
        "updated_at": now,
    }
    if getattr(op.get_context(), "as_sql", False):
        config_json = canonical.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{row['id']}', 'explain_sector_rules', '1.0.0', 'draft', "
            f"'{config_json}'::jsonb, '{row['configuration_hash']}', "
            f"'{row['created_at'].isoformat()}', '{row['updated_at'].isoformat()}')"
        )
    else:
        op.bulk_insert(table, [row])


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_config WHERE config_key='explain_sector_rules' AND version='1.0.0'"
    )
