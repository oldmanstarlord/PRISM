"""Add evidence-bound news impact records and draft configuration.

Revision ID: d2e3f4a5b621
Revises: c1d2e3f4a520
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

revision = "d2e3f4a5b621"
down_revision = "c1d2e3f4a520"
branch_labels = None
depends_on = None

CONFIG: dict[str, object] = {
    "approval_note": "Draft Step E4 exposure formula and wording; owner approval is required.",
    "path_weights": {"direct": 1.0, "rule": 0.85, "macro": 0.7, "spillover": 0.6},
    "base_confidence": {"direct": 0.95, "rule": 0.85, "macro": 0.7, "spillover": 0.65},
    "exposure_bands": {"medium_min": 0.35, "high_min": 0.65},
    "recency_half_life_days": 30.0,
    "direct_default_severity": 5.0,
    "spillover_min_r_squared": 0.25,
    "regression_window": 120,
    "maximum_stocks_per_item": 25,
    "minimum_confidence_to_display": 0.4,
    "unreviewed_rule_confidence_penalty": 0.25,
    "historical_min_analogues": 10,
    "historical_horizons": [0, 1, 5],
    "live_source_map": {"RBI": "news_rbi_rss", "SEBI": "news_sebi_rss", "PIB": "news_pib_rss"},
    "considerations": [
        "Check the portfolio weight held in the affected industries.",
        "Review whether exposed holdings share an MST cluster with a directly named stock.",
        "Monitor the linked macro indicators and their current stored regime.",
    ],
    "limitations": [
        "Possible effects come from versioned rules and stored statistical relationships; "
        "they are not predictions or investment advice.",
        "Rules marked UNREVIEWED receive lower confidence.",
        "Co-movement and shared clusters do not prove a business relationship or causation.",
        "Prices are end-of-day, not real-time.",
    ],
    "disclaimer": (
        "PRISM provides descriptive risk explanations, not investment advice or price predictions."
    ),
    "banned_phrases": [
        "buy",
        "sell",
        "price target",
        "will rise",
        "will fall",
        "guaranteed",
        "caused by",
    ],
}


def upgrade() -> None:
    op.add_column("policy_rule", sa.Column("macro_series_links", postgresql.JSONB(), nullable=True))
    op.create_table(
        "news_impact",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("news_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["news_item_id"], ["news_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "news_item_id",
            "config_fingerprint",
            "input_fingerprint",
            name="uq_news_impact_reproducible",
        ),
    )
    op.create_index("ix_news_impact_item_created", "news_impact", ["news_item_id", "created_at"])
    op.create_table(
        "news_impact_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("news_impact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("security_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("industry", sa.String(160), nullable=False),
        sa.Column("path_type", sa.String(20), nullable=False),
        sa.Column("transmission", postgresql.JSONB(), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("exposure_score", sa.Float(), nullable=False),
        sa.Column("exposure_band", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "path_type IN ('direct', 'rule', 'macro', 'spillover')", name="ck_news_impact_item_path"
        ),
        sa.CheckConstraint(
            "direction IN ('headwind', 'tailwind', 'ambiguous')",
            name="ck_news_impact_item_direction",
        ),
        sa.CheckConstraint(
            "exposure_score >= 0 AND exposure_score <= 1", name="ck_news_impact_item_exposure"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_news_impact_item_confidence"
        ),
        sa.ForeignKeyConstraint(["news_impact_id"], ["news_impact.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_impact_item_impact", "news_impact_item", ["news_impact_id"])
    op.create_index("ix_news_impact_item_security", "news_impact_item", ["security_id"])
    op.create_index("ix_news_impact_item_industry", "news_impact_item", ["industry"])

    canonical = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    now = datetime.now(UTC)
    config_id = uuid4()
    config_hash = hashlib.sha256(canonical.encode()).hexdigest()
    if getattr(op.get_context(), "as_sql", False):
        config_json = canonical.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config (id, config_key, version, status, configuration, "
            "configuration_hash, created_at, updated_at) "
            f"VALUES ('{config_id}', 'news_impact', '1.0.0', 'draft', "
            f"'{config_json}'::jsonb, '{config_hash}', '{now.isoformat()}', '{now.isoformat()}')"
        )
    else:
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
        op.bulk_insert(
            table,
            [
                {
                    "id": config_id,
                    "config_key": "news_impact",
                    "version": "1.0.0",
                    "status": "draft",
                    "configuration": CONFIG,
                    "configuration_hash": config_hash,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def downgrade() -> None:
    op.execute("DELETE FROM model_config WHERE config_key='news_impact' AND version='1.0.0'")
    op.drop_index("ix_news_impact_item_industry", table_name="news_impact_item")
    op.drop_index("ix_news_impact_item_security", table_name="news_impact_item")
    op.drop_index("ix_news_impact_item_impact", table_name="news_impact_item")
    op.drop_table("news_impact_item")
    op.drop_index("ix_news_impact_item_created", table_name="news_impact")
    op.drop_table("news_impact")
    op.drop_column("policy_rule", "macro_series_links")
