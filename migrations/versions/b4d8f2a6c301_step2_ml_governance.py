"""Add governed model metadata and explicit prediction statuses.

Revision ID: b4d8f2a6c301
Revises: a3c7e9f1b204
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4d8f2a6c301"
down_revision: str | None = "a3c7e9f1b204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "model_run", "training_window_start", existing_type=sa.Date(), nullable=True
    )
    op.alter_column(
        "model_run", "training_window_end", existing_type=sa.Date(), nullable=True
    )
    for _name, column in (
        ("model_type", sa.Column("model_type", sa.String(80))),
        ("methodology_version", sa.Column("methodology_version", sa.String(80))),
        ("feature_schema_version", sa.Column("feature_schema_version", sa.String(80))),
        ("source_data_version", sa.Column("source_data_version", sa.String(160))),
        ("validation_window_start", sa.Column("validation_window_start", sa.Date())),
        ("validation_window_end", sa.Column("validation_window_end", sa.Date())),
        ("test_window_start", sa.Column("test_window_start", sa.Date())),
        ("test_window_end", sa.Column("test_window_end", sa.Date())),
        (
            "preprocessing",
            sa.Column(
                "preprocessing", postgresql.JSONB(), server_default="{}", nullable=False
            ),
        ),
        (
            "baseline_comparison",
            sa.Column(
                "baseline_comparison", postgresql.JSONB(), server_default="{}", nullable=False
            ),
        ),
        ("artifact_path", sa.Column("artifact_path", sa.Text())),
        ("artifact_checksum", sa.Column("artifact_checksum", sa.String(64))),
        (
            "library_versions",
            sa.Column(
                "library_versions", postgresql.JSONB(), server_default="{}", nullable=False
            ),
        ),
        ("model_selected", sa.Column("model_selected", sa.String(80))),
        ("selection_reason", sa.Column("selection_reason", sa.Text())),
    ):
        op.add_column("model_run", column)

    op.alter_column(
        "model_prediction",
        "predicted_value",
        existing_type=sa.Numeric(16, 6),
        nullable=True,
    )
    op.add_column(
        "model_prediction",
        sa.Column("status", sa.String(30), server_default="ready", nullable=False),
    )
    op.add_column("model_prediction", sa.Column("failure_reason", sa.Text()))
    op.add_column("model_prediction", sa.Column("data_cutoff", sa.Date()))
    op.add_column("model_prediction", sa.Column("methodology_version", sa.String(80)))
    op.add_column("model_prediction", sa.Column("model_version", sa.String(80)))
    op.add_column("model_prediction", sa.Column("horizon_sessions", sa.Integer()))
    op.add_column("model_prediction", sa.Column("quality_status", sa.String(20)))
    op.create_unique_constraint(
        "uq_model_prediction_idempotent",
        "model_prediction",
        ["run_id", "target_type", "symbol", "prediction_date"],
    )
    op.create_check_constraint(
        "ck_model_run_status",
        "model_run",
        "status IN ('running', 'completed', 'ready', 'baseline_selected', "
        "'failed', 'untrained', 'insufficient_data', 'unavailable')",
    )
    op.create_check_constraint(
        "ck_model_run_training_window",
        "model_run",
        "training_window_end >= training_window_start",
    )
    op.create_check_constraint(
        "ck_model_prediction_status",
        "model_prediction",
        "status IN ('ready', 'stale', 'baseline_selected', 'failed', 'untrained', "
        "'insufficient_data', 'unavailable')",
    )
    op.create_check_constraint(
        "ck_model_prediction_bounds",
        "model_prediction",
        "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_model_prediction_bounds", "model_prediction", type_="check"
    )
    op.drop_constraint(
        "ck_model_prediction_status", "model_prediction", type_="check"
    )
    op.drop_constraint("ck_model_run_training_window", "model_run", type_="check")
    op.drop_constraint("ck_model_run_status", "model_run", type_="check")
    op.execute(
        "DELETE FROM model_run WHERE training_window_start IS NULL "
        "OR training_window_end IS NULL"
    )
    op.alter_column(
        "model_run", "training_window_end", existing_type=sa.Date(), nullable=False
    )
    op.alter_column(
        "model_run", "training_window_start", existing_type=sa.Date(), nullable=False
    )
    op.drop_constraint(
        "uq_model_prediction_idempotent", "model_prediction", type_="unique"
    )
    for name in (
        "quality_status",
        "horizon_sessions",
        "model_version",
        "methodology_version",
        "data_cutoff",
        "failure_reason",
        "status",
    ):
        op.drop_column("model_prediction", name)
    op.execute("DELETE FROM model_prediction WHERE predicted_value IS NULL")
    op.alter_column(
        "model_prediction",
        "predicted_value",
        existing_type=sa.Numeric(16, 6),
        nullable=False,
    )
    for name in (
        "selection_reason",
        "model_selected",
        "library_versions",
        "artifact_checksum",
        "artifact_path",
        "baseline_comparison",
        "preprocessing",
        "test_window_end",
        "test_window_start",
        "validation_window_end",
        "validation_window_start",
        "source_data_version",
        "feature_schema_version",
        "methodology_version",
        "model_type",
    ):
        op.drop_column("model_run", name)
