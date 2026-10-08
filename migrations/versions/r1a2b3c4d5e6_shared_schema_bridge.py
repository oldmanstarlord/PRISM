"""Bridge the independently deployed shared-database migration lineage.

Revision ID: r1a2b3c4d5e6
Revises: 9c41ad7b218e
Create Date: 2026-10-08

The shared Supabase database was advanced by an independent branch whose complete
migration files are not part of this repository. This marker lets the local lineage
converge on that deployed revision. The following migration performs conditional,
additive reconciliation and therefore also works for a clean local database where
the independently owned tables are absent.
"""

from collections.abc import Sequence

revision: str = "r1a2b3c4d5e6"
down_revision: str | None = "9c41ad7b218e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
