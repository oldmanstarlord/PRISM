"""Step 11: Timestamped news/policy items and explainable policy-to-sector rule table.

Revision ID: e1f2a3b4c511
Revises: d0e1f2a3b410
Create Date: 2026-10-05 23:30:00.000000

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
revision = "e1f2a3b4c511"
down_revision = "d0e1f2a3b410"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. news_item
    # -------------------------------------------------------------------------
    op.create_table(
        "news_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_news_item_published", "news_item", ["published_at"])
    op.create_index("ix_news_item_source", "news_item", ["source"])
    op.create_index("ix_news_item_content_hash", "news_item", ["content_hash"], unique=True)

    # -------------------------------------------------------------------------
    # 2. news_security_link
    # -------------------------------------------------------------------------
    op.create_table(
        "news_security_link",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "news_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("security.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_news_sec_link_sec", "news_security_link", ["security_id"])
    op.create_index("ix_news_sec_link_item", "news_security_link", ["news_item_id"])

    # -------------------------------------------------------------------------
    # 3. policy_rule
    # -------------------------------------------------------------------------
    op.create_table(
        "policy_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_key", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column(
            "match_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("match_category", sa.String(100), nullable=False),
        sa.Column(
            "affected_industries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("reviewer", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default=sa.text("'1.0.0'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_policy_rule_key", "policy_rule", ["rule_key"])
    op.create_index("ix_policy_rule_key_version", "policy_rule", ["rule_key", "version"])

    # -------------------------------------------------------------------------
    # 4. policy_event
    # -------------------------------------------------------------------------
    op.create_table(
        "policy_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "news_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("policy_rule.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("affected_industry", sa.String(100), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column(
            "evidence",
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
    op.create_index(
        "ix_policy_event_industry_matched",
        "policy_event",
        ["affected_industry", "matched_at"],
    )
    op.create_index("ix_policy_event_news", "policy_event", ["news_item_id"])
    op.create_index("ix_policy_event_rule", "policy_event", ["rule_id"])

    # -------------------------------------------------------------------------
    # 5. Seed ModelConfig for news_policy_pressure (D1)
    # -------------------------------------------------------------------------
    config_dict = {
        "component_id": "news_policy_pressure",
        "version": "1.0.0",
        "dimension": "macro",
        "default_weight": 0.05,
        "recency_half_life_days": 14,
        "lookback_days": 90,
        "poll_interval_seconds": 300,
        "headwind_multiplier": 1.0,
        "tailwind_mitigation_cap": 0.30,
        "description": (
            "Recency-decayed risk pressure from matched policy headlines and "
            "sector transmission rules."
        ),
    }
    cfg_json = json.dumps(config_dict, sort_keys=True)
    cfg_hash = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
    now_utc = datetime.now(UTC)

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
            f"VALUES ('{uuid4()}', 'news_policy_pressure', '1.0.0', 'approved', "
            f"'{cfg_json}'::jsonb, '{cfg_hash}', now(), now())"
        )
        op.execute(insert_sql)
    else:
        op.bulk_insert(
            model_config_table,
            [
                {
                    "id": uuid4(),
                    "config_key": "news_policy_pressure",
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
    # 6. Seed Score Component Definition (D2)
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
                "component_id": "news_policy_pressure",
                "dimension": "macro",
                "name": "News & Policy Pressure",
                "description": (
                    "Recency-decayed risk pressure from matched policy headlines and "
                    "sector transmission rules."
                ),
                "direction": "higher_is_riskier",
                "scope": "universe",
                "min_group_size": 5,
                "weight": 0.05,
                "active": True,
                "introduced_in_step": "Step 11",
            }
        ],
    )

    # -------------------------------------------------------------------------
    # 7. Seed 10 Draft Policy Rules (Authorized as DRAFT)
    # -------------------------------------------------------------------------
    rules_data = [
        (
            "POL_RBI_RATE_HIKE_V1",
            "RBI Repo Rate Hike & Monetary Tightening",
            ["repo rate", "rate hike", "monetary policy committee", "tightening stance"],
            "Monetary Policy",
            ["Financial Services", "Automobile and Auto Components", "Realty"],
            "headwind",
            7.0,
            (
                "Higher policy rates elevate funding costs, compress net interest margins for "
                "non-banks, and dampen interest-rate-sensitive credit demand."
            ),
        ),
        (
            "POL_RBI_UNSECURED_WEIGHTS_V1",
            "RBI Risk Weights Increase on Consumer Credit",
            ["risk weights", "unsecured retail loans", "consumer credit", "capital charge"],
            "Banking Regulation",
            ["Financial Services"],
            "headwind",
            8.0,
            (
                "Mandates higher regulatory capital allocations against unsecured credit "
                "portfolios, curbing loan growth and lowering returns on equity for retail lenders."
            ),
        ),
        (
            "POL_EXPORT_DUTY_COMMODITIES_V1",
            "Export Duties on Refined Fuels, Steel, and Ores",
            ["export duty", "windfall tax", "iron ore cess", "export levy"],
            "Trade & Customs",
            ["Oil, Gas & Consumable Fuels", "Metals & Mining"],
            "headwind",
            7.5,
            (
                "Export levies reduce overseas realization margins, force domestic market supply "
                "gluts, and compress operating margins for refiners and steelmakers."
            ),
        ),
        (
            "POL_PLI_SCHEME_EXPANSION_V1",
            "Production-Linked Incentive (PLI) Scheme Expansion",
            [
                "pli scheme",
                "production linked incentive",
                "incentive outlay",
                "semiconductor subsidy",
            ],
            "Industrial Subsidies",
            ["Consumer Durables", "Automobile and Auto Components", "Capital Goods"],
            "tailwind",
            6.5,
            (
                "Direct cash incentives on incremental sales boost operating cash flows, "
                "incentivize capex, and enhance export competitiveness for domestic manufacturers."
            ),
        ),
        (
            "POL_INFRA_CAPEX_BUDGET_V1",
            "Union Budget Capital Expenditure and Infrastructure Boost",
            [
                "capex outlay",
                "national infrastructure pipeline",
                "highway allocation",
                "railway capex",
            ],
            "Fiscal Policy",
            ["Construction", "Capital Goods", "Construction Materials"],
            "tailwind",
            7.0,
            (
                "Elevated central infrastructure capital expenditure accelerates order bookings, "
                "improves order execution velocity, and increases cement and steel consumption."
            ),
        ),
        (
            "POL_DEFENCE_INDIGENISATION_V1",
            "Positive Indigenisation List & Domestic Defence Procurement",
            [
                "indigenisation list",
                "defence acquisition council",
                "make in india defence",
                "domestic procurement",
            ],
            "Defence Policy",
            ["Capital Goods"],
            "tailwind",
            8.0,
            (
                "Mandatory domestic sourcing bans foreign imports for designated weapon systems, "
                "guaranteeing multi-year revenue visibility for Indian defence contractors."
            ),
        ),
        (
            "POL_PHARMA_PRICE_CONTROL_V1",
            "NLEM Price Capping & Essential Drug Price Controls",
            [
                "nlem",
                "national list of essential medicines",
                "nppa ceiling price",
                "drug price control",
            ],
            "Healthcare Regulation",
            ["Healthcare"],
            "headwind",
            6.5,
            (
                "Imposition of statutory price ceilings restricts pricing flexibility, eroding "
                "gross margins across chronic and acute domestic drug portfolios."
            ),
        ),
        (
            "POL_AGRI_EXPORT_RESTRICTION_V1",
            "Export Restrictions & Minimum Export Prices on Commodities",
            ["export ban", "minimum export price", "sugar export quota", "rice export restriction"],
            "Agriculture Policy",
            ["Fast Moving Consumer Goods"],
            "headwind",
            6.0,
            (
                "Disallows commodity producers from tapping higher international benchmark prices, "
                "depressing realization and expanding domestic working capital cycles."
            ),
        ),
        (
            "POL_RENEWABLE_RPO_MANDATE_V1",
            "Renewable Purchase Obligation Hikes & Green Energy Mandates",
            [
                "renewable purchase obligation",
                "rpo mandate",
                "green energy tariff",
                "solar capacity target",
            ],
            "Power Policy",
            ["Power", "Capital Goods"],
            "tailwind",
            6.5,
            (
                "Mandatory green power procurement enforces power purchase agreement signing, "
                "de-risking cash flows for renewable power producers and solar equipment suppliers."
            ),
        ),
        (
            "POL_DATA_PROTECTION_COMPLIANCE_V1",
            "Digital Personal Data Protection (DPDP) Compliance Mandates",
            ["dpdp act", "data protection board", "data fiduciary", "consent manager"],
            "Technology Regulation",
            ["Information Technology", "Financial Services"],
            "headwind",
            5.5,
            (
                "Strict statutory data processing guidelines elevate recurring compliance, legal "
                "audit, and server localization overhead for digital platforms and lenders."
            ),
        ),
    ]

    policy_rule_table = sa.table(
        "policy_rule",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("rule_key", sa.String),
        sa.column("description", sa.String),
        sa.column("match_keywords", postgresql.JSONB),
        sa.column("match_category", sa.String),
        sa.column("affected_industries", postgresql.JSONB),
        sa.column("direction", sa.String),
        sa.column("severity", sa.Float),
        sa.column("rationale", sa.Text),
        sa.column("reviewer", sa.String),
        sa.column("version", sa.String),
        sa.column("active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    if getattr(ctx, "as_sql", False):
        for r in rules_data:
            kw_sql = json.dumps(r[2]).replace("'", "''")
            ind_sql = json.dumps(r[4]).replace("'", "''")
            rat_sql = r[7].replace("'", "''")
            ins_sql = (
                "INSERT INTO policy_rule "
                "(id, rule_key, description, match_keywords, match_category, "
                "affected_industries, direction, severity, rationale, reviewer, "
                "version, active, created_at, updated_at) "
                f"VALUES ('{uuid4()}', '{r[0]}', '{r[1]}', '{kw_sql}'::jsonb, '{r[3]}', "
                f"'{ind_sql}'::jsonb, '{r[5]}', {r[6]}, '{rat_sql}', 'PRISM Policy Team', "
                "'1.0.0', false, now(), now())"
            )
            op.execute(ins_sql)
    else:
        op.bulk_insert(
            policy_rule_table,
            [
                {
                    "id": uuid4(),
                    "rule_key": r[0],
                    "description": r[1],
                    "match_keywords": r[2],
                    "match_category": r[3],
                    "affected_industries": r[4],
                    "direction": r[5],
                    "severity": r[6],
                    "rationale": r[7],
                    "reviewer": "PRISM Policy Team",
                    "version": "1.0.0",
                    "active": False,  # Seeded as DRAFT per authorization
                    "created_at": now_utc,
                    "updated_at": now_utc,
                }
                for r in rules_data
            ],
        )


def downgrade() -> None:
    op.drop_table("policy_event")
    op.drop_table("policy_rule")
    op.drop_table("news_security_link")
    op.drop_table("news_item")
