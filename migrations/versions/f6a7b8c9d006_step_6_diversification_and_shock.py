"""Step 6: Diversification run and shock scenario tables and model configs.

Revision ID: f6a7b8c9d006
Revises: e5f6a7b8c905
Create Date: 2026-10-05 18:30:00.000000
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d006"
down_revision: str | None = "e5f6a7b8c905"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. diversification_run
    op.create_table(
        "diversification_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_risk_run_id", sa.Uuid(), nullable=False),
        sa.Column("enb_eigen", sa.Numeric(12, 6), nullable=False),
        sa.Column("enb_risk_entropy", sa.Numeric(12, 6), nullable=False),
        sa.Column("cluster_weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_risk_run_id"], ["portfolio_risk_run.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_risk_run_id",
            "config_fingerprint",
            name="uq_diversification_run_portfolio_run_cfg",
        ),
    )
    op.create_index(
        "ix_diversification_run_portfolio_run_id",
        "diversification_run",
        ["portfolio_risk_run_id"],
    )

    # 2. shock_scenario
    op.create_table(
        "shock_scenario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("shocked_security_id", sa.Uuid(), nullable=True),
        sa.Column("shock_pct", sa.Numeric(8, 4), nullable=False),
        sa.Column("method_version", sa.String(80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shocked_security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shock_scenario_portfolio_id", "shock_scenario", ["portfolio_id"])

    # 3. shock_result
    op.create_table(
        "shock_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=True),
        sa.Column("weight", sa.Numeric(12, 8), nullable=False),
        sa.Column("estimated_impact_pct", sa.Numeric(12, 6), nullable=False),
        sa.Column("contribution_pct", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "method_detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["scenario_id"], ["shock_scenario.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shock_result_scenario_id", "shock_result", ["scenario_id"])
    op.create_index("ix_shock_result_security_id", "shock_result", ["security_id"])

    # 4. Seed model_config for portfolio_diversification
    div_cfg_payload = {
        "method_version": "diversification_v1",
        "enb_default": "entropy",
        "shrunk_correlation": True,
        "candidate_suggestion_rules": {
            "min_confidence": 60.0,
            "min_adv_20": 10000000.0,
            "max_candidates": 5,
        },
        "cluster_concentration_rules": {
            "high_concentration_threshold": 0.40,
        },
    }
    div_serialized = json.dumps(div_cfg_payload, sort_keys=True, separators=(",", ":"))
    div_cfg_hash = hashlib.sha256(div_serialized.encode("utf-8")).hexdigest()

    # 5. Seed model_config for shock_simulator
    shock_cfg_payload = {
        "method_version": "shock_regression_v1",
        "default_propagation": "regression_beta",
        "window_size": 250,
        "min_shock_pct": -50.0,
        "max_shock_pct": 50.0,
        "disclaimer_banner": "Scenario estimate, not a prediction",
        "mst_path_decay_enabled": True,
    }
    shock_serialized = json.dumps(shock_cfg_payload, sort_keys=True, separators=(",", ":"))
    shock_cfg_hash = hashlib.sha256(shock_serialized.encode("utf-8")).hexdigest()

    model_config_table = sa.table(
        "model_config",
        sa.column("id", sa.Uuid()),
        sa.column("config_key", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", sa.Text()),
        sa.column("configuration_hash", sa.String()),
        sa.column("approved_by", sa.String()),
        sa.column("approved_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        model_config_table,
        [
            {
                "id": uuid4(),
                "config_key": "portfolio_diversification",
                "version": "1.0.0",
                "status": "approved",
                "configuration": div_serialized,
                "configuration_hash": div_cfg_hash,
                "approved_by": "step_6_migration",
                "approved_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid4(),
                "config_key": "shock_simulator",
                "version": "1.0.0",
                "status": "approved",
                "configuration": shock_serialized,
                "configuration_hash": shock_cfg_hash,
                "approved_by": "step_6_migration",
                "approved_at": now,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("shock_result")
    op.drop_table("shock_scenario")
    op.drop_table("diversification_run")
