"""Add news_article, news_entity_match, and news_signal tables for Phase 5 news intelligence

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_article",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(160), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("publisher", sa.String(160), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(10),
            server_default="en",
            nullable=False,
        ),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("simhash", sa.String(64), nullable=True),
        sa.Column(
            "is_duplicate",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("primary_article_id", sa.Uuid(), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(40),
            server_default="processed",
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
        sa.ForeignKeyConstraint(
            ["primary_article_id"],
            ["news_article.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_news_article_url"),
    )
    op.create_index("ix_news_article_source_id", "news_article", ["source_id"])
    op.create_index("ix_news_article_published", "news_article", ["published_at"])
    op.create_index("ix_news_article_simhash", "news_article", ["simhash"])

    op.create_table(
        "news_entity_match",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("match_type", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column(
            "is_ambiguous",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(40),
            server_default="auto_matched",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["news_article.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_entity_match_article_id", "news_entity_match", ["article_id"])
    op.create_index("ix_news_entity_match_symbol", "news_entity_match", ["symbol"])
    op.create_index(
        "ix_news_entity_match_article_symbol",
        "news_entity_match",
        ["article_id", "symbol"],
    )

    op.create_table(
        "news_signal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(40), nullable=True),
        sa.Column(
            "is_market_wide",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("sentiment_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("sentiment_label", sa.String(20), nullable=False),
        sa.Column("sentiment_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("model_name", sa.String(80), nullable=False),
        sa.Column("model_version", sa.String(40), nullable=False),
        sa.Column("processing_time_ms", sa.Numeric(8, 2), nullable=False),
        sa.Column("event_category", sa.String(40), nullable=False),
        sa.Column("event_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["news_article.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_signal_article_id", "news_signal", ["article_id"])
    op.create_index("ix_news_signal_symbol", "news_signal", ["symbol"])
    op.create_index(
        "ix_news_signal_article_symbol",
        "news_signal",
        ["article_id", "symbol"],
    )


def downgrade() -> None:
    op.drop_table("news_signal")
    op.drop_table("news_entity_match")
    op.drop_table("news_article")
