"""Seed draft templates and thresholds for MST explanations.

Revision ID: f8a9b0c1d217
Revises: e7f8a9b0c116
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

revision = "f8a9b0c1d217"
down_revision = "e7f8a9b0c116"
branch_labels = None
depends_on = None

CONFIG: dict[str, object] = {
    "history_windows_count": 26,
    "rolling_correlation_days": 60,
    "event_lookback_days": 90,
    "max_chart_points": 120,
    "distance_scale": [
        {"correlation": 0.9, "distance": 0.447214, "label": "very close"},
        {"correlation": 0.5, "distance": 1.0, "label": "moderate"},
        {"correlation": 0.0, "distance": 1.414214, "label": "uncorrelated"},
    ],
    "stability_thresholds": {"high": 0.65, "medium": 0.45},
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
    "templates": {
        "edge_headline": "Why {a} and {b} are linked in the stored MST",
        "pair_headline": "Stored MST relationship between {a} and {b}",
        "node_headline": "Why {symbol} is a {node_role} in the stored MST",
        "kruskal": (
            "The edge was accepted at Kruskal step {step} of {edge_count}; it joined "
            "stored groups of {left_size} and {right_size} stocks at distance {distance}."
        ),
        "strength": (
            "{a} moves together with {b} at stored correlation {correlation}; the configured "
            "distance formula gives {distance}."
        ),
        "rank": "{b} ranked {rank_ab} for {a}, while {a} ranked {rank_ba} for {b}.",
        "industry_cluster": (
            "Same industry: {same_industry}; same stored cluster: {same_cluster} under "
            "{cluster_rule_version}."
        ),
        "residual": (
            "After removing the stored market factor, {a} moves together with {b} at "
            "residual correlation {residual_correlation}; residual-tree edge: {residual_edge}."
        ),
        "persistence": (
            "This edge appeared in {present_windows} of {total_windows} stored windows "
            "({persistence_pct}%)."
        ),
        "rolling_range": (
            "Across available stored windows, pair correlation ranged from {minimum} to "
            "{maximum}, with median {median}."
        ),
        "beta": (
            "Across {observations} stored observations, when {a} moved 10%, {b} moved about "
            "{ten_percent_effect}% on average; R-squared was {r_squared_pct}%."
        ),
        "path": (
            "The stored tree path has {hop_count} links: {path}; its weakest link has "
            "correlation {weakest_correlation}."
        ),
        "direct_pair": "Directly, {a} moves together with {b} at correlation {correlation}.",
        "node": (
            "{symbol} has degree {degree}, centrality percentile {centrality_percentile}, "
            "and belongs to a stored cluster of {cluster_size} stocks."
        ),
        "node_meaning": (
            "A hub is connected to several tree neighbours and may be inspected as a possible "
            "statistical transmission channel; this is not a causal claim."
        ),
        "node_neighbours": "Its nearest stored tree neighbours are {neighbours}.",
        "portfolio": (
            "In the loaded portfolio, {a} has weight {weight_a}% and risk contribution "
            "{risk_a}%; {b} has weight {weight_b}% and risk contribution {risk_b}%."
        ),
    },
    "limitations": [
        "MST links show statistical co-movement, not proof of a business relationship.",
        "The tree retains only N-1 links and omits many valid pairwise correlations.",
        "Historical beta, correlation and stability do not establish future effects.",
    ],
    "disclaimer": (
        "PRISM provides descriptive risk explanations, not investment advice or price predictions."
    ),
    "approval_note": "Draft user-facing MST explanation wording; owner review is required.",
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
    row = {
        "id": uuid4(),
        "config_key": "mst_explain_templates",
        "version": "1.0.0",
        "status": "draft",
        "configuration": CONFIG,
        "configuration_hash": hashlib.sha256(canonical.encode()).hexdigest(),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    if getattr(op.get_context(), "as_sql", False):
        config_json = canonical.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{row['id']}', 'mst_explain_templates', '1.0.0', 'draft', "
            f"'{config_json}'::jsonb, '{row['configuration_hash']}', "
            f"'{row['created_at'].isoformat()}', '{row['updated_at'].isoformat()}')"
        )
    else:
        op.bulk_insert(table, [row])


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_config WHERE config_key='mst_explain_templates' AND version='1.0.0'"
    )
