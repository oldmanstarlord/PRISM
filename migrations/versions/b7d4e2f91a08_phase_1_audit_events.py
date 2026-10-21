"""add owner-scoped Phase 1 audit events

Revision ID: b7d4e2f91a08
Revises: c6f2e9a1b304
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7d4e2f91a08"
down_revision: str | None = "c6f2e9a1b304"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_event_owner_id", "audit_event", ["owner_id"])
    op.create_index("ix_audit_event_owner_created", "audit_event", ["owner_id", "created_at"])
    op.create_index("ix_audit_event_entity", "audit_event", ["entity_type", "entity_id"])
    op.execute("ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $rls$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
               AND to_regprocedure('auth.uid()') IS NOT NULL THEN
                REVOKE ALL ON TABLE audit_event FROM anon;
                REVOKE ALL ON TABLE audit_event FROM authenticated;
                GRANT SELECT, INSERT ON TABLE audit_event TO authenticated;
                CREATE POLICY audit_event_owner_select ON audit_event FOR SELECT TO authenticated
                    USING ((SELECT auth.uid()) = owner_id);
                CREATE POLICY audit_event_owner_insert ON audit_event FOR INSERT TO authenticated
                    WITH CHECK ((SELECT auth.uid()) = owner_id);
            END IF;
        END
        $rls$;
        """
    )


def downgrade() -> None:
    op.drop_table("audit_event")
