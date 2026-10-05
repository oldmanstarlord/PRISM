"""Add nullable provenance source to macro observations.

Revision ID: f2a3b4c5d612
Revises: e1f2a3b4c511
Create Date: 2026-10-06 00:45:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d612"
down_revision = "e1f2a3b4c511"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add provenance without backfilling unverifiable existing rows."""
    op.add_column("macro_observation", sa.Column("source", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("macro_observation", "source")
