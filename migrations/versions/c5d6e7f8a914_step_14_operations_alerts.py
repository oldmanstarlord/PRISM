"""Add unattended operations, freshness, alerts, and watchlists.

Revision ID: c5d6e7f8a914
Revises: b4c5d6e7f813
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

revision = "c5d6e7f8a914"
down_revision = "b4c5d6e7f813"
branch_labels = None
depends_on = None

OPERATIONS_CONFIG: dict[str, object] = {
    "timezone": "Asia/Kolkata",
    "daily_run_hour": 19,
    "daily_run_minute": 0,
    "near_real_time_poll_minutes": 30,
    "daily_dag": [
        "ingest_prices",
        "crosscheck_prices",
        "sector_divergence",
        "mst",
        "mst_diagnostics",
        "macro",
        "regime",
        "fundamentals_governance",
        "stock_scores",
        "portfolio_reruns",
        "alert_evaluation",
    ],
    "retry": {"attempts": 3, "initial_wait_seconds": 2, "max_wait_seconds": 30},
    "freshness_sources": {
        "prices": {"expected_cadence_minutes": 1440, "grace_minutes": 720},
        "benchmark": {"expected_cadence_minutes": 1440, "grace_minutes": 720},
        "filings": {"expected_cadence_minutes": 30, "grace_minutes": 30},
        "news": {"expected_cadence_minutes": 30, "grace_minutes": 30},
        "macro": {"expected_cadence_minutes": 1440, "grace_minutes": 1440},
    },
    "alert_rules": {
        "risk_jump": {"threshold": 10.0, "cooldown_minutes": 1440},
        "confidence_drop": {"threshold": 15.0, "cooldown_minutes": 1440},
        "stale_data": {"threshold": 1.0, "cooldown_minutes": 240},
        "negative_event": {"threshold": 8.0, "cooldown_minutes": 1440},
        "regime_change": {"threshold": 1.0, "cooldown_minutes": 1440},
        "mst_cluster_change": {"threshold": 1.0, "cooldown_minutes": 1440},
    },
    "watchlist_default_thresholds": {"risk_jump": 10.0, "confidence_drop": 15.0},
    "price_frequency_label": "End-of-day prices",
    "limitations": [
        "Prices are end-of-day and are not real-time.",
        "Filings and news polling latency depends on source availability.",
        "Alerts are descriptive risk notifications, not investment advice.",
    ],
}


def _insert_config() -> None:
    payload = json.dumps(OPERATIONS_CONFIG, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
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
    if getattr(op.get_context(), "as_sql", False):
        escaped = payload.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{uuid4()}', 'operations_parameters', '1.0.0', 'approved', "
            f"'{escaped}'::jsonb, '{fingerprint}', now(), now())"
        )
    else:
        now = datetime.now(UTC)
        op.bulk_insert(
            table,
            [
                {
                    "id": uuid4(),
                    "config_key": "operations_parameters",
                    "version": "1.0.0",
                    "status": "approved",
                    "configuration": OPERATIONS_CONFIG,
                    "configuration_hash": fingerprint,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def upgrade() -> None:
    op.add_column("score_run", sa.Column("parent_run_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "score_run", sa.Column("run_kind", sa.String(30), server_default="full", nullable=False)
    )
    op.create_foreign_key(
        "fk_score_run_parent",
        "score_run",
        "score_run",
        ["parent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_score_run_parent_run_id", "score_run", ["parent_run_id"])
    op.create_table(
        "data_freshness",
        sa.Column("source_key", sa.String(80), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_data_date", sa.Date()),
        sa.Column("expected_cadence", sa.Integer(), nullable=False),
        sa.Column("grace", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_index("ix_data_freshness_status", "data_freshness", ["status"])
    op.create_table(
        "alert",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject_type", sa.String(40), nullable=False),
        sa.Column("subject_id", sa.String(120), nullable=False),
        sa.Column("alert_type", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("inputs_ref", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("status", sa.String(30), server_default="open", nullable=False),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True)),
        sa.Column("config_version", sa.String(40), nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("dedup_key", name="uq_alert_dedup_key"),
    )
    op.create_index("ix_alert_latest", "alert", ["status", "created_at"])
    op.create_table(
        "watchlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "watchlist_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "watchlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("watchlist.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("thresholds", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("watchlist_id", "security_id", name="uq_watchlist_item_security"),
    )
    op.create_index("ix_watchlist_item_watchlist_id", "watchlist_item", ["watchlist_id"])
    op.create_index("ix_watchlist_item_security_id", "watchlist_item", ["security_id"])
    _insert_config()


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_config WHERE config_key='operations_parameters' AND version='1.0.0'"
    )
    op.drop_table("watchlist_item")
    op.drop_table("watchlist")
    op.drop_table("alert")
    op.drop_table("data_freshness")
    op.drop_index("ix_score_run_parent_run_id", table_name="score_run")
    op.drop_constraint("fk_score_run_parent", "score_run", type_="foreignkey")
    op.drop_column("score_run", "run_kind")
    op.drop_column("score_run", "parent_run_id")
