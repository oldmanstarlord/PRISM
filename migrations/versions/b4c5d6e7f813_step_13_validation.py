"""Add honest validation persistence and versioned parameters.

Revision ID: b4c5d6e7f813
Revises: a3b4c5d6e712
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

revision = "b4c5d6e7f813"
down_revision = "a3b4c5d6e712"
branch_labels = None
depends_on = None

VALIDATION_CONFIG: dict[str, object] = {
    "monthly_frequency": 1,
    "target_horizon_trading_days": 20,
    "worst_return_window_days": 5,
    "minimum_cross_section": 5,
    "walk_forward_min_train_periods": 12,
    "walk_forward_test_periods": 3,
    "walk_forward_step_periods": 3,
    "walk_forward_embargo_periods": 1,
    "confidence_bin_edges": [0.0, 40.0, 60.0, 80.0, 101.0],
    "random_seed": 13013,
    "layer1_sigma_bands": [1.0, 2.0, 3.0],
    "survivorship_warning": (
        "Historical validation uses current NIFTY 200 membership only; results contain "
        "survivorship bias and must not be presented as investable backtests."
    ),
    "limitations": [
        "Short available point-in-time history can make estimates unstable.",
        "Forward 20-day labels overlap across monthly dates when sessions overlap.",
        "Validation measures descriptive risk ordering, not return prediction or advice.",
    ],
}


def upgrade() -> None:
    op.create_table(
        "validation_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
        sa.Column("period", sa.String(80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.UniqueConstraint(
            "kind", "config_fingerprint", "period", name="uq_validation_run_reproducible"
        ),
    )
    op.create_index("ix_validation_run_latest", "validation_run", ["kind", "completed_at"])
    op.create_table(
        "validation_result",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(100), nullable=False),
        sa.Column("component_key", sa.String(100), server_default="score", nullable=False),
        sa.Column("value", sa.Float()),
        sa.Column("baseline_value", sa.Float()),
        sa.Column("n", sa.Integer(), server_default="0", nullable=False),
        sa.Column("period", sa.String(80), nullable=False),
        sa.UniqueConstraint(
            "run_id",
            "metric_key",
            "component_key",
            "period",
            name="uq_validation_result_metric",
        ),
    )
    op.create_index("ix_validation_result_run_id", "validation_result", ["run_id"])
    op.create_index(
        "ix_validation_result_run_metric", "validation_result", ["run_id", "metric_key"]
    )
    op.create_table(
        "experiment_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("variants_tried", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
    )
    op.create_index("ix_experiment_log_created", "experiment_log", ["created_at"])

    payload = json.dumps(VALIDATION_CONFIG, sort_keys=True, separators=(",", ":"))
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
    now = datetime.now(UTC)
    context = op.get_context()
    if getattr(context, "as_sql", False):
        escaped = payload.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{uuid4()}', 'validation_parameters', '1.0.0', 'draft', "
            f"'{escaped}'::jsonb, '{fingerprint}', now(), now())"
        )
    else:
        op.bulk_insert(
            table,
            [
                {
                    "id": uuid4(),
                    "config_key": "validation_parameters",
                    "version": "1.0.0",
                    "status": "draft",
                    "configuration": VALIDATION_CONFIG,
                    "configuration_hash": fingerprint,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM model_config WHERE config_key = 'validation_parameters' "
        "AND version = '1.0.0'"
    )
    op.drop_index("ix_experiment_log_created", table_name="experiment_log")
    op.drop_table("experiment_log")
    op.drop_index("ix_validation_result_run_metric", table_name="validation_result")
    op.drop_index("ix_validation_result_run_id", table_name="validation_result")
    op.drop_table("validation_result")
    op.drop_index("ix_validation_run_latest", table_name="validation_run")
    op.drop_table("validation_run")
