"""phase 1 authenticated portfolio input

Revision ID: c6f2e9a1b304
Revises: 9c41ad7b218e
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6f2e9a1b304"
down_revision: str | None = "9c41ad7b218e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_SQL = """
ALTER TABLE portfolio ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_holding ENABLE ROW LEVEL SECURITY;

DO $rls$
DECLARE
    table_name text;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
       AND to_regprocedure('auth.uid()') IS NOT NULL THEN
        FOREACH table_name IN ARRAY ARRAY['portfolio', 'portfolio_snapshot', 'portfolio_holding']
        LOOP
            EXECUTE format('REVOKE ALL ON TABLE %I FROM anon', table_name);
            EXECUTE format('REVOKE ALL ON TABLE %I FROM authenticated', table_name);
            EXECUTE format(
                'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I TO authenticated',
                table_name
            );
            EXECUTE format(
                'CREATE POLICY %I ON %I FOR SELECT TO authenticated '
                'USING ((SELECT auth.uid()) = owner_id)',
                table_name || '_owner_select', table_name
            );
            EXECUTE format(
                'CREATE POLICY %I ON %I FOR INSERT TO authenticated '
                'WITH CHECK ((SELECT auth.uid()) = owner_id)',
                table_name || '_owner_insert', table_name
            );
            EXECUTE format(
                'CREATE POLICY %I ON %I FOR UPDATE TO authenticated '
                'USING ((SELECT auth.uid()) = owner_id) '
                'WITH CHECK ((SELECT auth.uid()) = owner_id)',
                table_name || '_owner_update', table_name
            );
            EXECUTE format(
                'CREATE POLICY %I ON %I FOR DELETE TO authenticated '
                'USING ((SELECT auth.uid()) = owner_id)',
                table_name || '_owner_delete', table_name
            );
        END LOOP;
    END IF;
END
$rls$;
"""


def upgrade() -> None:
    op.create_table(
        "portfolio",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("input_mode", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "input_mode IN ('quantities', 'weights')", name="ck_portfolio_input_mode"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_owner_id", "portfolio", ["owner_id"])
    op.create_index("ix_portfolio_owner_archived", "portfolio", ["owner_id", "archived_at"])
    op.create_table(
        "portfolio_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("cash_amount", sa.Numeric(24, 8), server_default="0", nullable=False),
        sa.Column("cash_weight", sa.Numeric(18, 12), server_default="0", nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("source", sa.String(20), server_default="csv", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("cash_amount >= 0", name="ck_snapshot_cash_amount"),
        sa.CheckConstraint(
            "cash_weight >= 0 AND cash_weight <= 1", name="ck_snapshot_cash_weight"
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_snapshot_portfolio_id", "portfolio_snapshot", ["portfolio_id"])
    op.create_index("ix_portfolio_snapshot_owner", "portfolio_snapshot", ["owner_id"])
    op.create_index(
        "ix_portfolio_snapshot_latest", "portfolio_snapshot", ["portfolio_id", "created_at"]
    )
    op.create_table(
        "portfolio_holding",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8)),
        sa.Column("target_weight", sa.Numeric(18, 12)),
        sa.CheckConstraint(
            "(quantity IS NOT NULL AND quantity > 0 AND target_weight IS NULL) OR "
            "(target_weight IS NOT NULL AND target_weight > 0 AND target_weight <= 1 "
            "AND quantity IS NULL)",
            name="ck_portfolio_holding_value",
        ),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["portfolio_snapshot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "security_id", name="uq_portfolio_snapshot_security"),
    )
    op.create_index("ix_portfolio_holding_snapshot_id", "portfolio_holding", ["snapshot_id"])
    op.create_index("ix_portfolio_holding_owner", "portfolio_holding", ["owner_id"])
    op.create_index("ix_portfolio_holding_security_id", "portfolio_holding", ["security_id"])
    op.execute(RLS_SQL)


def downgrade() -> None:
    op.drop_table("portfolio_holding")
    op.drop_table("portfolio_snapshot")
    op.drop_table("portfolio")
