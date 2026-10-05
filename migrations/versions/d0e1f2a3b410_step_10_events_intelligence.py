"""Step 10: Announcements become explainable events and events component (dimension: events).

Revision ID: d0e1f2a3b410
Revises: c9d0e1f2a309
Create Date: 2026-10-05 22:50:00.000000

Tables added (additive only):
  - event_rule: rule-based category mapping to canonical event types (D1)
  - event_item: point-in-time company announcements with effective trading date (D4)
  - text_score: FinBERT / rule-based sentiment and evidence text scoring (D3)

Config seeded:
  - event_risk_pressure (version 1.0.0, approved)

Components seeded:
  - event_risk_pressure (dimension: events, active=True)
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d0e1f2a3b410"
down_revision = "c9d0e1f2a309"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. event_rule
    # -------------------------------------------------------------------------
    op.create_table(
        "event_rule",
        sa.Column("rule_key", sa.String(100), primary_key=True),
        sa.Column("source_category", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("risk_relevant", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default=sa.text("'v1.0.0'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_event_rule_source_cat", "event_rule", ["source_category"])
    op.create_index("ix_event_rule_event_type", "event_rule", ["event_type"])

    # -------------------------------------------------------------------------
    # 2. event_item
    # -------------------------------------------------------------------------
    op.create_table(
        "event_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_document.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column(
            "event_type_method",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'rule'"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_trading_date", sa.Date(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column(
            "importance_components",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_event_item_sec_pub", "event_item", ["security_id", "published_at"])
    op.create_index(
        "ix_event_item_effective", "event_item", ["security_id", "effective_trading_date"]
    )
    op.create_index("ix_event_item_event_type", "event_item", ["event_type"])
    op.create_index("ix_event_item_source_doc", "event_item", ["source_document_id"])

    # -------------------------------------------------------------------------
    # 3. text_score
    # -------------------------------------------------------------------------
    op.create_table(
        "text_score",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("event_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(80), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("sentiment", sa.String(20), nullable=False),
        sa.Column("p_pos", sa.Float(), nullable=False),
        sa.Column("p_neg", sa.Float(), nullable=False),
        sa.Column("p_neu", sa.Float(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=True),
        sa.Column("importance", sa.Float(), nullable=True),
        sa.Column("evidence_span", sa.Text(), nullable=True),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_text_score_item_model",
        "text_score",
        ["item_id", "model_name", "model_version"],
    )

    # -------------------------------------------------------------------------
    # 4. Seed Canonical Model Config (D1)
    # -------------------------------------------------------------------------
    config_dict = {
        "description": "Step 10 Event Intelligence and Recency-Decayed Risk Pressure",
        "finbert_enabled": False,
        "finbert_model_id": "ProsusAI/finbert",
        "finbert_revision": "90eb618b0f7ca7067d2feae4d588523ee734c5db",
        "max_token_chunks": 512,
        "recency_half_life_days": 14,
        "positive_offset_cap": 0.30,
        "importance_weights": {
            "regulatory_action": 10.0,
            "debt_rating": 8.5,
            "results": 8.0,
            "management_change": 7.0,
            "promoter_insider": 6.5,
            "ma_order": 5.0,
            "dividend": 3.0,
            "other": 2.0,
        },
        "magnitude_multipliers": {
            "auditor_resignation": 1.5,
            "ceo_resignation": 1.3,
            "cfo_resignation": 1.3,
            "credit_downgrade": 1.4,
            "credit_upgrade": 1.0,
            "default": 2.0,
            "regulatory_penalty": 1.5,
            "standard": 1.0,
        },
        "market_close_time_ist": "15:30:00",
    }
    cfg_json = json.dumps(config_dict, sort_keys=True, separators=(",", ": "))
    cfg_hash = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
    now_utc = datetime.now(UTC)

    # Seed model_config
    model_config_table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.Text()),
        sa.column("version", sa.Text()),
        sa.column("status", sa.Text()),
        sa.column("configuration", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("configuration_hash", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    ctx = op.get_context()
    if getattr(ctx, "as_sql", False):
        insert_sql = (
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, "
            "configuration_hash, created_at, updated_at) "
            f"VALUES ('{uuid4()}', 'event_risk_pressure', '1.0.0', 'approved', "
            f"'{cfg_json}'::jsonb, '{cfg_hash}', now(), now())"
        )
        op.execute(insert_sql)
    else:
        op.bulk_insert(
            model_config_table,
            [
                {
                    "id": uuid4(),
                    "config_key": "event_risk_pressure",
                    "version": "1.0.0",
                    "status": "approved",
                    "configuration": config_dict,
                    "configuration_hash": cfg_hash,
                    "created_at": now_utc,
                    "updated_at": now_utc,
                }
            ],
        )

    # -------------------------------------------------------------------------
    # 5. Seed Score Component Definition (D2)
    # -------------------------------------------------------------------------
    component_def_table = sa.table(
        "score_component_definition",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("component_id", sa.Text()),
        sa.column("dimension", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("direction", sa.Text()),
        sa.column("scope", sa.Text()),
        sa.column("min_group_size", sa.Integer()),
        sa.column("weight", sa.Float()),
        sa.column("active", sa.Boolean()),
        sa.column("introduced_in_step", sa.Text()),
    )
    op.bulk_insert(
        component_def_table,
        [
            {
                "id": uuid4(),
                "component_id": "event_risk_pressure",
                "dimension": "events",
                "name": "Event Risk Pressure",
                "description": (
                    "Recency-decayed pressure from exchange corporate announcements, "
                    "weighted by event type, parsed severity, and sentiment direction."
                ),
                "direction": "higher_is_riskier",
                "scope": "universe",
                "min_group_size": 5,
                "weight": 1.0,
                "active": True,
                "introduced_in_step": "Step 10",
            }
        ],
    )

    # -------------------------------------------------------------------------
    # 6. Seed Default Event Rules (D1)
    # -------------------------------------------------------------------------
    rules_data = [
        (
            "REGULATORY_ACTION",
            "Regulatory Action / Penalties",
            "regulatory_action",
            True,
            "negative",
        ),
        ("SEBI_ORDER", "SEBI Orders / Show Cause", "regulatory_action", True, "negative"),
        ("CREDIT_RATING", "Credit Rating Action", "debt_rating", True, "negative"),
        ("DEBT_DEFAULT", "Default in Payment / Debt Servicing", "debt_rating", True, "negative"),
        (
            "FINANCIAL_RESULTS",
            "Financial Results / Earnings Announcement",
            "results",
            True,
            "negative",
        ),
        ("BOARD_MEETING_RESULTS", "Board Meeting for Results", "results", False, "neutral"),
        (
            "MGMT_RESIGNATION",
            "Resignation of Director / KMP / Auditor",
            "management_change",
            True,
            "negative",
        ),
        (
            "MGMT_APPOINTMENT",
            "Appointment of Director / KMP",
            "management_change",
            False,
            "positive",
        ),
        (
            "INSIDER_PLEDGE",
            "Pledge / Release of Promoter Shares",
            "promoter_insider",
            True,
            "negative",
        ),
        ("ORDER_WIN", "Award of Order / New Project", "ma_order", False, "positive"),
        (
            "MERGER_ACQUISITION",
            "Mergers, Acquisitions and Restructuring",
            "ma_order",
            True,
            "negative",
        ),
        ("DIVIDEND_DECLARED", "Dividend / Buyback Declaration", "dividend", False, "positive"),
        ("GENERAL_ANNOUNCEMENT", "General Compliance Announcement", "other", False, "neutral"),
    ]

    event_rule_table = sa.table(
        "event_rule",
        sa.column("rule_key", sa.String),
        sa.column("source_category", sa.String),
        sa.column("event_type", sa.String),
        sa.column("risk_relevant", sa.Boolean),
        sa.column("direction", sa.String),
        sa.column("version", sa.String),
        sa.column("active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        event_rule_table,
        [
            {
                "rule_key": f"rule_{item[0].lower()}_v1",
                "source_category": item[1],
                "event_type": item[2],
                "risk_relevant": item[3],
                "direction": item[4],
                "version": "v1.0.0",
                "active": True,
                "created_at": now_utc,
            }
            for item in rules_data
        ],
    )


def downgrade() -> None:
    op.drop_table("text_score")
    op.drop_table("event_item")
    op.drop_table("event_rule")
