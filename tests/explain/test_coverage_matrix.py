"""Coverage matrix and evidence-binding test suite for PRISM explanations (Step E6).

Verifies:
1. Coverage matrix of subject_type x section across all registered explainers.
2. Sections without evidence are omitted and flagged with a limitation line.
3. Strict invariant: no sentence exists without evidence_ids.
4. Every referenced evidence_id exists in payload.evidence.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from backend.app.explain.alert import AlertExplainer, AlertSubject
from backend.app.explain.evidence import Evidence
from backend.app.explain.guardrails import apply_payload_guardrails, evidence_bound_sentences
from backend.app.explain.registry import registry
from backend.app.explain.schemas import (
    ExplanationSentence,
)
from backend.app.explain.shock import ShockExplainer, ShockSubject
from migrations.versions.e3f4a5b6c722_step_e5_extended_explanations import (
    CONFIG as E5_CONFIG,
)

EXPECTED_SUBJECT_TYPES = [
    "risk_component",
    "mst_edge",
    "mst_node",
    "mst_pair",
    "sector_divergence",
    "sector",
    "news",
    "shock",
    "diversification",
    "score_change",
    "alert",
]


def test_registry_contains_all_subject_types() -> None:
    """Verify that all 11 required subject types are present in ExplainerRegistry."""
    for st in EXPECTED_SUBJECT_TYPES:
        explainer = registry.get(st)
        assert explainer is not None
        assert explainer.subject_type == st


def test_no_sentence_exists_without_evidence_ids_in_guardrails() -> None:
    """Invariant: ExplanationSentence strictly rejects empty evidence_ids via schema validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="List should have at least 1 item"):
        ExplanationSentence(text="Sentence with no evidence.", evidence_ids=[])

    config = {
        "banned_phrases": [],
        "correlation_required_phrase": "moves together with",
    }
    valid_ids = {"ev_1", "ev_2"}

    sentences = [
        ExplanationSentence(text="Sentence with valid evidence.", evidence_ids=["ev_1"]),
        ExplanationSentence(
            text="Sentence with mixed evidence.", evidence_ids=["ev_1", "ev_missing"]
        ),
    ]

    filtered = evidence_bound_sentences(sentences, valid_ids, config)
    assert len(filtered) == 1
    assert filtered[0].text == "Sentence with valid evidence."
    assert filtered[0].evidence_ids == ["ev_1"]


def test_payload_sentences_all_have_valid_evidence_ids() -> None:
    """Assert across sample payloads that every sentence has non-empty valid evidence_ids."""
    as_of = date(2026, 1, 15)

    shock_sub = ShockSubject(
        holding_symbol="INFY",
        shocked_symbol="NIFTY",
        shock_pct=-5.0,
        method="regression_beta",
    )
    ev_shock = [
        Evidence(
            evidence_id="shock:impact",
            kind="statistic",
            label="Predicted Move",
            value=-4.85,
            source_table="shock_result",
            source_ref="INFY",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:sensitivity",
            kind="statistic",
            label="Sensitivity Beta",
            value=0.97,
            source_table="price_daily_adjusted",
            source_ref="beta",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:r_squared",
            kind="statistic",
            label="R-Squared",
            value=74.0,
            source_table="price_daily_adjusted",
            source_ref="r2",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:weight",
            kind="statistic",
            label="Weight",
            value=12.5,
            source_table="portfolio_holding",
            source_ref="wt",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:contribution",
            kind="statistic",
            label="Contribution",
            value=-0.61,
            source_table="shock_result",
            source_ref="contrib",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:path",
            kind="rule",
            label="Path",
            value="Direct equity market index exposure moves together with empirical market beta",
            source_table="shock_scenario",
            source_ref="path",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:linear",
            kind="config",
            label="Linear",
            value="Asset sensitivity estimated over trailing 126 days is assumed constant.",
            source_table="model_config",
            source_ref="cfg",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:liquidity",
            kind="config",
            label="Liquidity",
            value="Prices adjust without order-book slippage or liquidation cascades.",
            source_table="model_config",
            source_ref="cfg",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:stability",
            kind="config",
            label="Stability",
            value="Historical dependence structure holds during hypothetical shock scenario.",
            source_table="model_config",
            source_ref="cfg",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:isolated",
            kind="config",
            label="Isolated",
            value=(
                "Hypothetical stress is isolated to NIFTY without "
                "independent contemporaneous shocks."
            ),
            source_table="model_config",
            source_ref="cfg",
            as_of=as_of,
        ),
    ]
    p_shock = ShockExplainer().compose(ev_shock, E5_CONFIG, "1.0.0", shock_sub)
    guarded = apply_payload_guardrails(p_shock, E5_CONFIG)

    valid_ids = {e.evidence_id for e in guarded.evidence}

    # Summary sentences
    for s in guarded.summary_points:
        assert s.evidence_ids, f"Summary sentence '{s.text}' has no evidence_ids"
        assert all(eid in valid_ids for eid in s.evidence_ids)

    # Section sentences
    for sec in guarded.sections:
        for s in sec.sentences:
            assert s.evidence_ids, f"Section '{sec.title}' sentence '{s.text}' has no evidence_ids"
            assert all(eid in valid_ids for eid in s.evidence_ids)

    # Confidence reasons
    for s in guarded.confidence.reasons:
        assert s.evidence_ids, f"Confidence reason '{s.text}' has no evidence_ids"
        assert all(eid in valid_ids for eid in s.evidence_ids)


def test_missing_evidence_omits_sentences_and_retains_limitations() -> None:
    """When evidence is missing from payload, guardrails omit unsupported sentences."""
    as_of = date(2026, 1, 15)
    alert_id = uuid4()
    alt_sub = AlertSubject(alert_id=alert_id)

    ev_alt = [
        Evidence(
            evidence_id="alert:rule",
            kind="rule",
            label="Rule",
            value="volatility_spike",
            source_table="alert",
            source_ref="rule",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:severity",
            kind="config",
            label="Severity",
            value="high",
            source_table="alert",
            source_ref="sev",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:reason",
            kind="rule",
            label="Reason",
            value="30-day realized volatility jumped 45% week-over-week",
            source_table="alert",
            source_ref="reason",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:observed",
            kind="statistic",
            label="Observed",
            value="42.1",
            source_table="alert",
            source_ref="obs",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:threshold",
            kind="config",
            label="Threshold",
            value="35.0",
            source_table="alert",
            source_ref="thresh",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:status",
            kind="rule",
            label="Status",
            value="active",
            source_table="alert",
            source_ref="stat",
            as_of=as_of,
        ),
    ]

    p_alt = AlertExplainer().compose(ev_alt, E5_CONFIG, "1.0.0", alt_sub)
    guarded_full = apply_payload_guardrails(p_alt, E5_CONFIG)

    all_sentence_eids = [
        eid
        for sec in guarded_full.sections
        for s in sec.sentences
        for eid in s.evidence_ids
    ]
    assert "alert:rule" in all_sentence_eids
    assert "alert:status" in all_sentence_eids

    # Simulate omission of 'alert:rule' from stored evidence
    p_alt_dropped = p_alt.model_copy(
        update={"evidence": [e for e in p_alt.evidence if e.evidence_id != "alert:rule"]}
    )
    guarded_dropped = apply_payload_guardrails(p_alt_dropped, E5_CONFIG)

    dropped_eids = [
        eid
        for sec in guarded_dropped.sections
        for s in sec.sentences
        for eid in s.evidence_ids
    ]
    # Sentence referencing alert:rule is omitted
    assert "alert:rule" not in dropped_eids
    # Sentence referencing alert:status remains
    assert "alert:status" in dropped_eids
    # Configured limitations remain intact
    assert len(guarded_dropped.limitations) >= 1


def test_guardrails_drop_unsupported_sentences_from_payload() -> None:
    """When a sentence in payload references an unbacked evidence ID, guardrails omit it."""
    as_of = date(2026, 1, 15)
    alert_id = uuid4()
    alt_sub = AlertSubject(alert_id=alert_id)

    # Compose valid payload
    ev = [
        Evidence(
            evidence_id="alert:rule",
            kind="rule",
            label="Rule",
            value="volatility_spike",
            source_table="alert",
            source_ref="rule",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:severity",
            kind="config",
            label="Severity",
            value="high",
            source_table="alert",
            source_ref="sev",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:reason",
            kind="rule",
            label="Reason",
            value="30-day realized volatility jumped 45%",
            source_table="alert",
            source_ref="reason",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:observed",
            kind="statistic",
            label="Observed",
            value="42.1",
            source_table="alert",
            source_ref="obs",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:threshold",
            kind="config",
            label="Threshold",
            value="35.0",
            source_table="alert",
            source_ref="thresh",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="alert:status",
            kind="rule",
            label="Status",
            value="active",
            source_table="alert",
            source_ref="stat",
            as_of=as_of,
        ),
    ]
    payload = AlertExplainer().compose(ev, E5_CONFIG, "1.0.0", alt_sub)

    # Intentionally corrupt payload evidence by removing 'alert:reason' from evidence list
    corrupted_payload = payload.model_copy(
        update={
            "evidence": [
                item for item in payload.evidence if item.evidence_id != "alert:reason"
            ]
        }
    )

    guarded = apply_payload_guardrails(corrupted_payload, E5_CONFIG)

    # Any sentence that referenced alert:reason must be dropped
    for s in guarded.summary_points:
        assert "alert:reason" not in s.evidence_ids
    for sec in guarded.sections:
        for s in sec.sentences:
            assert "alert:reason" not in s.evidence_ids

