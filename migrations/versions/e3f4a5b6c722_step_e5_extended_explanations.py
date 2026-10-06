"""Add Step E5 extended explanation templates and glossary terms.

Revision ID: e3f4a5b6c722
Revises: d2e3f4a5b621
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

revision = "e3f4a5b6c722"
down_revision = "d2e3f4a5b621"
branch_labels = None
depends_on = None

DISCLAIMER = (
    "PRISM provides descriptive risk explanations, not investment advice or price predictions."
)

CONFIG: dict[str, object] = {
    "approval_note": (
        "Step E5 extended explainers for shock, diversification, score-change, and alerts."
    ),
    "shock": {
        "headline": (
            "Scenario Shock Transmission for {holding} under {shock_pct}% Shock to {shocked_symbol}"
        ),
        "summary_templates": {
            "impact": (
                "Holding {holding} has an estimated scenario impact of {impact_pct}% "
                "under a {shock_pct}% shock to {shocked_symbol}."
            ),
            "sensitivity": (
                "The sensitivity of {holding} to {shocked_symbol} is {sensitivity} "
                "({sensitivity_type}), where higher positive values indicate it "
                "moves together with {shocked_symbol}."
            ),
            "r_squared": (
                "The historical co-movement explains an R-squared of {r_squared_pct}% "
                "of {holding}'s return variance over the trailing window."
            ),
        },
        "detail_templates": {
            "contribution": (
                "Holding {holding} has a portfolio weight of {weight_pct}%, "
                "contributing {contribution_pct}% to total portfolio loss."
            ),
            "transmission_path": "Transmission path: {path_description}.",
        },
    },
    "diversification": {
        "headline": "Portfolio Diversification & Effective Number of Bets Analysis",
        "summary_templates": {
            "enb_entropy": (
                "The portfolio delivers {enb_entropy} effective bets based on "
                "risk-contribution entropy across {holding_count} holdings."
            ),
            "enb_eigen": (
                "The eigenvalue-derived effective bets is {enb_eigen}, reflecting "
                "statistical dimensionality of co-movement."
            ),
            "dominant_cluster": (
                "The primary risk cluster is {dominant_cluster}, accounting for "
                "{dominant_cluster_weight}% of portfolio capital."
            ),
        },
        "detail_templates": {
            "computation": (
                "Risk entropy is computed via exp(-sum(p_i * ln(p_i))) where p_i "
                "is each asset's percentage risk contribution."
            ),
            "cluster_hhi": (
                "Cluster concentration exhibits an HHI of {cluster_hhi}, with "
                "{cluster_count} active MST clusters."
            ),
        },
    },
    "score_change": {
        "headline": "Risk Score Trajectory for {symbol}",
        "summary_templates": {
            "score_delta": (
                "Total risk score changed by {score_delta} points (from {previous_score} "
                "to {current_score}) between {previous_date} and {current_date}."
            ),
            "primary_driver": (
                "The leading driver of the change was {top_component}, which shifted "
                "by {top_component_points} points (pct change: {top_component_percentile})."
            ),
        },
        "detail_templates": {
            "second_driver": (
                "Secondary contributor: {second_component} shifted by "
                "{second_component_points} points."
            ),
            "third_driver": (
                "Tertiary contributor: {third_component} shifted by "
                "{third_component_points} points."
            ),
        },
    },
    "alert": {
        "headline": "Alert Explanation: {alert_type_label} on {subject_label}",
        "summary_templates": {
            "trigger": (
                "Alert triggered because observed {metric_label} ({observed_value}) "
                "exceeded configured threshold ({threshold_value})."
            ),
            "context": "Context: {reason}",
        },
        "detail_templates": {
            "status": "Current alert status is {status}, created at {created_at}.",
            "inputs": "Evaluation inputs: {inputs_summary}.",
        },
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
            "PRISM explanations describe empirical risk associations and scenario simulations; "
            "they are not investment advice or price predictions."
        ),
        "Statistical co-movement does not imply a causal relationship or guaranteed performance.",
        "Shock propagation estimates rely on historical dependence without liquidity feedback.",
        "Prices are end-of-day closing prices, not real-time intraday quotes.",
    ],
    "disclaimer": DISCLAIMER,
}

NEW_GLOSSARY_TERMS: list[tuple[str, str, str, str | None, list[str]]] = [
    (
        "mst_path_decay",
        "MST path decay",
        (
            "The attenuated transmission factor along the unique path connecting two assets in "
            "the Minimum Spanning Tree, computed as the product of positive edge weights."
        ),
        "D(s, j) = prod max(0, rho_uv)",
        ["correlation", "minimum_spanning_tree"],
    ),
    (
        "entropy",
        "Entropy",
        (
            "A mathematical measure of dispersion or uniformity across portfolio percentage "
            "risk contributions; higher entropy indicates more balanced risk."
        ),
        "H = - sum(p_i * ln(p_i))",
        ["effective_number_of_bets", "diversification"],
    ),
    (
        "eigenvalue",
        "Eigenvalue",
        (
            "A scalar reflecting the variance explained along an uncorrelated principal "
            "dimension of the portfolio correlation matrix."
        ),
        "det(Sigma - lambda * I) = 0",
        ["effective_number_of_bets", "correlation"],
    ),
    (
        "score_change",
        "Score change",
        (
            "The net shift in total risk score between successive evaluation dates, "
            "decomposed into individual component contributions."
        ),
        "Delta S = S_t - S_{t-1}",
        ["risk_score", "component_weight"],
    ),
]


def upgrade() -> None:
    canonical = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    now = datetime.now(UTC)
    config_id = uuid4()
    config_hash = hashlib.sha256(canonical.encode()).hexdigest()

    if getattr(op.get_context(), "as_sql", False):
        config_json = canonical.replace("'", "''").replace(":", r"\:")
        op.execute(
            "INSERT INTO model_config (id, config_key, version, status, configuration, "
            "configuration_hash, created_at, updated_at) "
            f"VALUES ('{config_id}', 'explain_extended_templates', '1.0.0', 'draft', "
            f"'{config_json}'::jsonb, '{config_hash}', '{now.isoformat()}', '{now.isoformat()}')"
        )
        for term_key, label, plain_def, formula, see_also in NEW_GLOSSARY_TERMS:
            term_id = uuid4()
            see_also_json = json.dumps(see_also)
            plain_escaped = plain_def.replace("'", "''")
            label_escaped = label.replace("'", "''")
            formula_val = f"'{formula}'" if formula else "NULL"
            op.execute(
                "INSERT INTO glossary_term "
                "(id, term_key, label, plain_definition, formula_text, see_also, version) "
                f"VALUES ('{term_id}', '{term_key}', '{label_escaped}', '{plain_escaped}', "
                f"{formula_val}, '{see_also_json}'::jsonb, '1.0.0') "
                "ON CONFLICT (term_key, version) DO NOTHING"
            )
    else:
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
        op.bulk_insert(
            table,
            [
                {
                    "id": config_id,
                    "config_key": "explain_extended_templates",
                    "version": "1.0.0",
                    "status": "draft",
                    "configuration": CONFIG,
                    "configuration_hash": config_hash,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )

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
        op.bulk_insert(
            glossary_table,
            [
                {
                    "id": uuid4(),
                    "term_key": term_key,
                    "label": label,
                    "plain_definition": plain_def,
                    "formula_text": formula,
                    "see_also": see_also,
                    "version": "1.0.0",
                }
                for term_key, label, plain_def, formula, see_also in NEW_GLOSSARY_TERMS
            ],
        )


def downgrade() -> None:
    for term_key, _, _, _, _ in NEW_GLOSSARY_TERMS:
        op.execute(
            f"DELETE FROM glossary_term WHERE term_key = '{term_key}' AND version = '1.0.0'"
        )
    op.execute(
        "DELETE FROM model_config "
        "WHERE config_key = 'explain_extended_templates' AND version = '1.0.0'"
    )
