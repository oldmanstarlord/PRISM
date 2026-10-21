"""reconcile authenticated portfolio input with the shared portfolio schema

Revision ID: c6f2e9a1b304
Revises: r1a2b3c4d5e6
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6f2e9a1b304"
down_revision: str | None = "r1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = ["portfolio", "portfolio_snapshot", "portfolio_snapshot_holding"]


def _reconcile_portfolio() -> None:
    # This is raw PostgreSQL DDL so the migration remains renderable in offline mode
    # while safely handling both clean databases and the independently deployed schema.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio (
            id uuid PRIMARY KEY,
            name varchar(120) NOT NULL,
            description text,
            owner_ref varchar(120) NOT NULL DEFAULT 'local-user',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz
        );
        ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS owner_id uuid;
        ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS input_mode varchar(20)
            NOT NULL DEFAULT 'weights';
        ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS currency varchar(3)
            NOT NULL DEFAULT 'INR';
        ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS archived_at timestamptz;
        CREATE INDEX IF NOT EXISTS ix_portfolio_owner_ref ON portfolio (owner_ref);
        CREATE INDEX IF NOT EXISTS ix_portfolio_owner_id ON portfolio (owner_id);
        CREATE INDEX IF NOT EXISTS ix_portfolio_owner_archived
            ON portfolio (owner_id, archived_at);
        DO $constraint$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_portfolio_input_mode'
                  AND conrelid = 'portfolio'::regclass
            ) THEN
                ALTER TABLE portfolio ADD CONSTRAINT ck_portfolio_input_mode
                    CHECK (input_mode IN ('quantities', 'weights'));
            END IF;
        END
        $constraint$;
        """
    )


def _enable_owner_rls() -> None:
    table_list = ", ".join(f"'{table}'" for table in RLS_TABLES)
    op.execute(
        f"""
        DO $rls$
        DECLARE table_name text;
        BEGIN
            FOREACH table_name IN ARRAY ARRAY[{table_list}]
            LOOP
                EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
            END LOOP;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
               AND to_regprocedure('auth.uid()') IS NOT NULL THEN
                FOREACH table_name IN ARRAY ARRAY[{table_list}]
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
    )


def upgrade() -> None:
    _reconcile_portfolio()
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
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("cash_amount >= 0", name="ck_snapshot_cash_amount"),
        sa.CheckConstraint("cash_weight >= 0 AND cash_weight <= 1", name="ck_snapshot_cash_weight"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_snapshot_portfolio_id", "portfolio_snapshot", ["portfolio_id"])
    op.create_index("ix_portfolio_snapshot_owner", "portfolio_snapshot", ["owner_id"])
    op.create_index(
        "ix_portfolio_snapshot_latest", "portfolio_snapshot", ["portfolio_id", "created_at"]
    )
    op.create_table(
        "portfolio_snapshot_holding",
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
            name="ck_portfolio_snapshot_holding_value",
        ),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["portfolio_snapshot.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "security_id", name="uq_portfolio_snapshot_holding_security"
        ),
    )
    op.create_index(
        "ix_portfolio_snapshot_holding_snapshot_id",
        "portfolio_snapshot_holding",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_portfolio_snapshot_holding_owner", "portfolio_snapshot_holding", ["owner_id"]
    )
    op.create_index(
        "ix_portfolio_snapshot_holding_security_id",
        "portfolio_snapshot_holding",
        ["security_id"],
    )
    _enable_owner_rls()


def downgrade() -> None:
    op.drop_table("portfolio_snapshot_holding")
    op.drop_table("portfolio_snapshot")
    # Preserve the independently owned portfolio table and legacy rows. Only remove
    # columns introduced by this reconciliation.
    op.execute("DROP INDEX IF EXISTS ix_portfolio_owner_archived")
    op.execute("DROP INDEX IF EXISTS ix_portfolio_owner_id")
    op.execute("ALTER TABLE portfolio DROP CONSTRAINT IF EXISTS ck_portfolio_input_mode")
    op.execute("ALTER TABLE portfolio DROP COLUMN IF EXISTS archived_at")
    op.execute("ALTER TABLE portfolio DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE portfolio DROP COLUMN IF EXISTS input_mode")
    op.execute("ALTER TABLE portfolio DROP COLUMN IF EXISTS owner_id")
