"""complete Layer 2 persistence

Revision ID: 9c41ad7b218e
Revises: 4a78e8c0c741
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c41ad7b218e"
down_revision: str | None = "4a78e8c0c741"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mst_run", sa.Column("data_cutoff", sa.DateTime(timezone=True)))
    op.add_column(
        "mst_run",
        sa.Column("is_acyclic", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "mst_run",
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column("mst_run", sa.Column("configuration_hash", sa.String(64)))
    op.add_column("mst_run", sa.Column("input_fingerprint", sa.String(64)))
    op.add_column(
        "mst_run",
        sa.Column("status", sa.String(30), server_default="legacy", nullable=False),
    )
    op.create_unique_constraint(
        "uq_mst_reproducible_run",
        "mst_run",
        ["window_end", "implementation_version", "configuration_hash", "input_fingerprint"],
    )
    op.create_index("ix_mst_run_latest", "mst_run", ["status", "window_end", "computed_at"])
    op.create_table(
        "mst_node",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mst_run_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("industry", sa.String(160), nullable=False),
        sa.Column("observations_used", sa.Integer(), nullable=False),
        sa.Column("membership_source", sa.String(120), nullable=False),
        sa.ForeignKeyConstraint(["mst_run_id"], ["mst_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mst_run_id", "security_id", name="uq_mst_run_node"),
    )
    op.create_index("ix_mst_node_mst_run_id", "mst_node", ["mst_run_id"])
    op.add_column("mst_edge", sa.Column("symbol_a", sa.String(40)))
    op.add_column("mst_edge", sa.Column("symbol_b", sa.String(40)))
    op.add_column("mst_edge", sa.Column("paired_observations", sa.Integer()))


def downgrade() -> None:
    op.drop_column("mst_edge", "paired_observations")
    op.drop_column("mst_edge", "symbol_b")
    op.drop_column("mst_edge", "symbol_a")
    op.drop_index("ix_mst_node_mst_run_id", table_name="mst_node")
    op.drop_table("mst_node")
    op.drop_index("ix_mst_run_latest", table_name="mst_run")
    op.drop_constraint("uq_mst_reproducible_run", "mst_run", type_="unique")
    op.drop_column("mst_run", "status")
    op.drop_column("mst_run", "input_fingerprint")
    op.drop_column("mst_run", "configuration_hash")
    op.drop_column("mst_run", "configuration")
    op.drop_column("mst_run", "is_acyclic")
    op.drop_column("mst_run", "data_cutoff")
