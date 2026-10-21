"""Step 4: Multi-User Persistence and Data Security

Revision ID: c5e9f3b7a402
Revises: b4d8f2a6c301
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e9f3b7a402"
down_revision: str | None = "b4d8f2a6c301"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Journal Notes
    op.create_table(
        "journal_note",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_journal_note_owner", "journal_note", ["owner_id"], unique=False)
    op.create_index("ix_journal_note_symbol", "journal_note", ["symbol"], unique=False)
    op.create_index(
        "ix_journal_note_owner_symbol",
        "journal_note",
        ["owner_id", "symbol"],
        unique=False,
    )

    # 2. Journal Decisions
    op.create_table(
        "journal_decision",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("decision_type", sa.String(length=20), nullable=False),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "decision_type IN ('BUY', 'HOLD', 'SELL', 'REVIEW')",
            name="ck_journal_decision_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_journal_decision_owner", "journal_decision", ["owner_id"], unique=False)
    op.create_index("ix_journal_decision_symbol", "journal_decision", ["symbol"], unique=False)
    op.create_index(
        "ix_journal_decision_owner_symbol",
        "journal_decision",
        ["owner_id", "symbol"],
        unique=False,
    )
    op.create_index(
        "ix_journal_decision_owner_date",
        "journal_decision",
        ["owner_id", "decision_date"],
        unique=False,
    )

    # 3. PortfolioRiskHistory additions
    op.add_column(
        "portfolio_risk_history",
        sa.Column(
            "methodology_version",
            sa.String(length=40),
            server_default="1.0.0",
            nullable=False,
        ),
    )
    op.add_column(
        "portfolio_risk_history",
        sa.Column("data_cutoff", sa.Date(), nullable=True),
    )

    # 4. PortfolioTransaction idempotency
    op.add_column(
        "portfolio_transaction",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_portfolio_transaction_idempotency",
        "portfolio_transaction",
        ["portfolio_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_transaction_idempotency", table_name="portfolio_transaction"
    )
    op.drop_column("portfolio_transaction", "idempotency_key")
    op.drop_column("portfolio_risk_history", "data_cutoff")
    op.drop_column("portfolio_risk_history", "methodology_version")
    op.drop_table("journal_decision")
    op.drop_table("journal_note")
