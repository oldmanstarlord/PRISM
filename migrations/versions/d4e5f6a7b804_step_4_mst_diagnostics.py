"""Step 4: MST stability, clustering, and node metrics schema and seed.

Revision ID: d4e5f6a7b804
Revises: c3d4e5f6a703
Create Date: 2026-10-05 01:10:00.000000
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b804"
down_revision: str | None = "c3d4e5f6a703"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. mst_stability
    op.create_table(
        "mst_stability",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("prior_run_id", sa.Uuid(), nullable=False),
        sa.Column("edge_persistence", sa.Numeric(8, 6), nullable=False),
        sa.Column("node_overlap", sa.Numeric(8, 6), nullable=False),
        sa.Column("window_gap_days", sa.Integer(), nullable=False),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["prior_run_id"], ["mst_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["mst_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "prior_run_id", name="uq_mst_stability_runs"),
    )
    op.create_index("ix_mst_stability_run_id", "mst_stability", ["run_id"])
    op.create_index("ix_mst_stability_prior_run_id", "mst_stability", ["prior_run_id"])

    # 2. mst_cluster
    op.create_table(
        "mst_cluster",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("cluster_id", sa.String(80), nullable=False),
        sa.Column("cluster_rule_version", sa.String(80), nullable=False),
        sa.Column("cluster_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["mst_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "security_id", "cluster_rule_version", name="uq_mst_cluster_node_rule"
        ),
    )
    op.create_index("ix_mst_cluster_run_id", "mst_cluster", ["run_id"])
    op.create_index("ix_mst_cluster_sec_id", "mst_cluster", ["security_id"])
    op.create_index("ix_mst_cluster_cluster_id", "mst_cluster", ["cluster_id"])

    # 3. mst_node_metric
    op.create_table(
        "mst_node_metric",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("degree", sa.Integer(), nullable=False),
        sa.Column("weighted_centrality", sa.Numeric(12, 8), nullable=False),
        sa.Column("hub_rank", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["mst_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "security_id", name="uq_mst_node_metric_run_sec"),
    )
    op.create_index("ix_mst_node_metric_run_id", "mst_node_metric", ["run_id"])
    op.create_index("ix_mst_node_metric_sec_id", "mst_node_metric", ["security_id"])
    op.create_index("ix_mst_node_metric_symbol", "mst_node_metric", ["symbol"])

    # 4. Seed model_config: mst_diagnostics
    mst_config_payload = {
        "history_windows_count": 26,
        "cluster_rule": "remove_k_longest_edges",
        "cluster_rule_version": "longest-k-edges-v1",
        "cluster_k_cut": 10,
        "stability_thresholds": {
            "high": 0.65,
            "medium": 0.45,
        },
        "default_variant": "raw",
    }
    serialized_cfg = json.dumps(mst_config_payload, sort_keys=True, separators=(",", ":"))
    cfg_hash = hashlib.sha256(serialized_cfg.encode("utf-8")).hexdigest()

    model_config_table = sa.table(
        "model_config",
        sa.column("id", sa.Uuid()),
        sa.column("config_key", sa.String),
        sa.column("version", sa.String),
        sa.column("status", sa.String),
        sa.column("configuration", postgresql.JSONB()),
        sa.column("configuration_hash", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        model_config_table,
        [
            {
                "id": uuid4(),
                "config_key": "mst_diagnostics",
                "version": "1.0.0",
                "status": "approved",
                "configuration": mst_config_payload,
                "configuration_hash": cfg_hash,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("mst_node_metric")
    op.drop_table("mst_cluster")
    op.drop_table("mst_stability")
