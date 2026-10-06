"""Add evidence-bound explanations and versioned glossary.

Revision ID: e7f8a9b0c116
Revises: d6e7f8a9b015
Create Date: 2026-10-06
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e7f8a9b0c116"
down_revision = "d6e7f8a9b015"
branch_labels = None
depends_on = None

DISCLAIMER = (
    "PRISM provides descriptive risk explanations, not investment advice or price predictions."
)

EXPLAIN_TEMPLATES: dict[str, object] = {
    "component": {
        "headline": "{component_label} for {symbol}",
        "summary_templates": {
            "value": "The stored component value was {raw_value}{unit_suffix}.",
            "percentile": (
                "The value ranked at the {percentile}th percentile in its scoring peer set."
            ),
            "points": "The component received {points} risk points before dimension aggregation.",
        },
        "detail_templates": {
            "direction_weight": (
                "Its configured direction was {direction_label} and its component "
                "weight was {weight}."
            ),
            "status_age": "Its stored status was {status}, with data age of {data_age_days} days.",
            "window": "The stored calculation window was {window}.",
        },
    },
    "wording_bands": {
        "correlation_strength": [
            {"maximum": 0.2, "label": "very weak"},
            {"maximum": 0.4, "label": "weak"},
            {"maximum": 0.6, "label": "moderate"},
            {"maximum": 0.8, "label": "strong"},
            {"maximum": 1.0, "label": "very strong"},
        ]
    },
    "banned_phrases": [
        "buy",
        "sell",
        "hold",
        "price target",
        "will rise",
        "will fall",
        "guaranteed",
        "because of correlation",
        "caused by",
    ],
    "correlation_required_phrase": "moves together with",
    "limitations": [
        (
            "The explanation is limited to stored component evidence available "
            "at the score run cutoff."
        ),
        "Percentile and points describe relative risk inputs; they do not predict returns.",
    ],
    "disclaimer": DISCLAIMER,
    "approval_note": "Draft user-facing wording; owner review is required before approval.",
}

GLOSSARY: list[tuple[str, str, str, str | None, list[str]]] = [
    (
        "correlation",
        "Correlation",
        "A statistic describing how two series move together.",
        None,
        ["correlation_distance"],
    ),
    (
        "correlation_distance",
        "Correlation distance",
        "A non-negative transformation of correlation used to construct the approved network.",
        "sqrt(2 * (1 - correlation))",
        ["correlation", "minimum_spanning_tree"],
    ),
    (
        "minimum_spanning_tree",
        "Minimum spanning tree",
        "A sparse network connecting every stock while minimizing total configured edge distance.",
        None,
        ["correlation_distance", "hub"],
    ),
    (
        "hub",
        "Hub",
        "A node with relatively many or important links in the stored network.",
        None,
        ["minimum_spanning_tree", "cluster"],
    ),
    (
        "cluster",
        "Cluster",
        "A group identified from stored statistical relationships; it is not a causal group.",
        None,
        ["correlation", "hub"],
    ),
    (
        "residual",
        "Residual",
        "The part of an observed value left after subtracting the fitted model component.",
        None,
        ["r_squared", "beta"],
    ),
    (
        "z_score",
        "Z-score",
        "The number of standard deviations a value lies above or below its reference mean.",
        "(value - mean) / standard_deviation",
        ["volatility"],
    ),
    (
        "beta",
        "Beta",
        "A fitted measure of how strongly an asset's returns move with a benchmark's returns.",
        None,
        ["r_squared", "correlation"],
    ),
    (
        "r_squared",
        "R-squared",
        "The share of observed variation described by a fitted model in the stored sample.",
        None,
        ["beta", "residual"],
    ),
    (
        "percentile",
        "Percentile",
        (
            "The percentage of comparable observations at or below a value under "
            "the configured tie rule."
        ),
        None,
        ["risk_score"],
    ),
    (
        "risk_contribution",
        "Risk contribution",
        "A holding's allocated share of the portfolio risk measure under the configured method.",
        None,
        ["component_weight", "concentration"],
    ),
    (
        "effective_number_of_bets",
        "Effective number of bets",
        (
            "A diversification measure expressing how many similarly sized independent "
            "risk allocations would give comparable concentration."
        ),
        None,
        ["diversification", "concentration"],
    ),
    (
        "regime",
        "Market regime",
        "A descriptive label assigned from configured market-state indicators and thresholds.",
        None,
        ["volatility", "correlation"],
    ),
    (
        "value_at_risk",
        "Value at Risk (VaR)",
        (
            "A loss threshold associated with a stated horizon, confidence level, "
            "and estimation method."
        ),
        None,
        ["expected_shortfall", "tail_loss"],
    ),
    (
        "expected_shortfall",
        "Expected shortfall",
        (
            "The average loss beyond the configured Value at Risk threshold in the "
            "reference sample or model."
        ),
        None,
        ["value_at_risk", "tail_loss"],
    ),
    (
        "drawdown",
        "Drawdown",
        "The percentage decline from a previous running peak to a later value.",
        None,
        ["tail_loss"],
    ),
    (
        "volatility",
        "Volatility",
        (
            "The dispersion of returns over a stated window, usually annualised "
            "using a documented factor."
        ),
        None,
        ["z_score", "regime"],
    ),
    (
        "confidence",
        "Confidence",
        (
            "A data-quality and model-reliability indicator, not a probability that "
            "a prediction is correct."
        ),
        None,
        ["data_age"],
    ),
    (
        "data_age",
        "Data age",
        "Elapsed calendar days between the effective result date and the stored input date.",
        None,
        ["confidence"],
    ),
    (
        "component_weight",
        "Component weight",
        "The configured relative influence of a component within its aggregation step.",
        None,
        ["risk_contribution", "risk_score"],
    ),
    (
        "risk_score",
        "Risk score",
        "A descriptive composite of registered risk components under a versioned configuration.",
        None,
        ["percentile", "component_weight"],
    ),
    (
        "liquidity",
        "Liquidity",
        "The observed ability to trade value without relying on price-direction predictions.",
        None,
        ["concentration"],
    ),
    (
        "concentration",
        "Concentration",
        (
            "The extent to which exposure is dominated by a small number of holdings, "
            "sectors, or clusters."
        ),
        None,
        ["diversification", "effective_number_of_bets"],
    ),
    (
        "tail_loss",
        "Tail loss",
        "Loss behaviour in the more adverse part of the observed return distribution.",
        None,
        ["value_at_risk", "expected_shortfall"],
    ),
    (
        "diversification",
        "Diversification",
        (
            "The distribution of exposure across holdings and risk relationships; "
            "it does not guarantee lower loss."
        ),
        None,
        ["concentration", "effective_number_of_bets"],
    ),
]


def _insert_config() -> None:
    payload = json.dumps(EXPLAIN_TEMPLATES, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    table = sa.table(
        "model_config",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("config_key", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", postgresql.JSONB()),
        sa.column("configuration_hash", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    if getattr(op.get_context(), "as_sql", False):
        escaped = payload.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config "
            "(id, config_key, version, status, configuration, configuration_hash, "
            "created_at, updated_at) "
            f"VALUES ('{uuid4()}', 'explain_templates', '1.0.0', 'draft', "
            f"'{escaped}'::jsonb, '{fingerprint}', now(), now())"
        )
    else:
        op.bulk_insert(
            table,
            [
                {
                    "id": uuid4(),
                    "config_key": "explain_templates",
                    "version": "1.0.0",
                    "status": "draft",
                    "configuration": EXPLAIN_TEMPLATES,
                    "configuration_hash": fingerprint,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )


def upgrade() -> None:
    op.create_table(
        "explanation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("subject_type", sa.String(60), nullable=False),
        sa.Column("subject_key", sa.String(180), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("template_version", sa.String(40), nullable=False),
        sa.Column("config_fingerprint", sa.String(64), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "subject_type",
            "subject_key",
            "as_of",
            "template_version",
            "input_fingerprint",
            name="uq_explanation_reproducible",
        ),
    )
    op.create_index(
        "ix_explanation_subject_latest", "explanation", ["subject_type", "subject_key", "as_of"]
    )
    op.create_table(
        "glossary_term",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("term_key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("plain_definition", sa.Text(), nullable=False),
        sa.Column("formula_text", sa.Text()),
        sa.Column("see_also", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.UniqueConstraint("term_key", "version", name="uq_glossary_term_version"),
    )
    op.create_index("ix_glossary_term_key", "glossary_term", ["term_key"])
    glossary_table = sa.table(
        "glossary_term",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("term_key", sa.String()),
        sa.column("label", sa.String()),
        sa.column("plain_definition", sa.Text()),
        sa.column("formula_text", sa.Text()),
        sa.column("see_also", postgresql.JSONB()),
        sa.column("version", sa.String()),
    )
    rows = [
        {
            "id": uuid4(),
            "term_key": key,
            "label": label,
            "plain_definition": definition,
            "formula_text": formula,
            "see_also": see_also,
            "version": "1.0.0",
        }
        for key, label, definition, formula, see_also in GLOSSARY
    ]
    if getattr(op.get_context(), "as_sql", False):
        for row in rows:
            key = str(row["term_key"]).replace("'", "''")
            label = str(row["label"]).replace("'", "''")
            definition = str(row["plain_definition"]).replace("'", "''")
            formula_value = row["formula_text"]
            formula_sql = (
                "NULL"
                if formula_value is None
                else "'" + str(formula_value).replace("'", "''") + "'"
            )
            see_also_json = json.dumps(row["see_also"], separators=(",", ":"))
            op.execute(
                "INSERT INTO glossary_term "
                "(id, term_key, label, plain_definition, formula_text, see_also, version) "
                f"VALUES ('{row['id']}', '{key}', '{label}', '{definition}', "
                f"{formula_sql}, '{see_also_json}'::jsonb, '1.0.0')"
            )
    else:
        op.bulk_insert(glossary_table, rows)
    _insert_config()


def downgrade() -> None:
    op.execute("DELETE FROM model_config WHERE config_key='explain_templates' AND version='1.0.0'")
    op.drop_index("ix_glossary_term_key", table_name="glossary_term")
    op.drop_table("glossary_term")
    op.drop_index("ix_explanation_subject_latest", table_name="explanation")
    op.drop_table("explanation")
