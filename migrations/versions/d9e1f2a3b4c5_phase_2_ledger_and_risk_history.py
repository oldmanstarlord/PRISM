"""add owner-scoped Phase 2 transaction ledger and portfolio risk history

Revision ID: d9e1f2a3b4c5
Revises: b7d4e2f91a08
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d9e1f2a3b4c5"
down_revision: str | None = "b7d4e2f91a08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE_2_RLS_TABLES = ["portfolio_transaction", "portfolio_risk_history"]


def upgrade() -> None:
    op.create_table(
        "portfolio_transaction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("security_id", sa.Uuid(), nullable=True),
        sa.Column("symbol", sa.String(40), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("price", sa.Numeric(20, 6), nullable=True),
        sa.Column("amount", sa.Numeric(24, 8), nullable=False),
        sa.Column("fees", sa.Numeric(20, 6), server_default="0", nullable=False),
        sa.Column("realized_pnl", sa.Numeric(24, 8), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "transaction_type IN ('BUY', 'SELL', 'FEES', 'DIVIDEND', 'DEPOSIT', 'WITHDRAWAL')",
            name="ck_transaction_type",
        ),
        sa.CheckConstraint("fees >= 0", name="ck_transaction_fees"),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_transaction_quantity"),
        sa.CheckConstraint("price IS NULL OR price > 0", name="ck_transaction_price"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["security_id"], ["security.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_transaction_portfolio_id", "portfolio_transaction", ["portfolio_id"]
    )
    op.create_index("ix_portfolio_transaction_owner_id", "portfolio_transaction", ["owner_id"])
    op.create_index(
        "ix_portfolio_transaction_security_id", "portfolio_transaction", ["security_id"]
    )
    op.create_index(
        "ix_portfolio_transaction_portfolio_date",
        "portfolio_transaction",
        ["portfolio_id", "trade_date"],
    )

    op.create_table(
        "portfolio_risk_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("portfolio_risk_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("portfolio_classification", sa.String(30), nullable=False),
        sa.Column("annualized_volatility", sa.Numeric(12, 6), nullable=False),
        sa.Column("downside_volatility", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_drawdown", sa.Numeric(12, 6), nullable=False),
        sa.Column("diversification_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("effective_holdings", sa.Numeric(10, 4), nullable=False),
        sa.Column("top_sector", sa.String(160), nullable=False),
        sa.Column("top_sector_weight", sa.Numeric(8, 4), nullable=False),
        sa.Column("largest_holding", sa.String(40), nullable=False),
        sa.Column("largest_holding_weight", sa.Numeric(8, 4), nullable=False),
        sa.Column(
            "indicators_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["portfolio_snapshot.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_risk_history_portfolio_id", "portfolio_risk_history", ["portfolio_id"]
    )
    op.create_index("ix_portfolio_risk_history_owner_id", "portfolio_risk_history", ["owner_id"])
    op.create_index(
        "ix_portfolio_risk_history_portfolio_date",
        "portfolio_risk_history",
        ["portfolio_id", "valuation_date"],
    )

    table_list = ", ".join(f"'{t}'" for t in PHASE_2_RLS_TABLES)
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


def downgrade() -> None:
    op.drop_table("portfolio_risk_history")
    op.drop_table("portfolio_transaction")
