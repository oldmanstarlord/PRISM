"""Wording and non-causal guard test suite for PRISM explanations (Step E6).

Scans every template, glossary entry, and sample generated explanation for
banned phrases (buy, sell, hold, target price, guaranteed, will rise, will fall,
you should invest) and forbidden causal phrases (because of, caused by, will cause,
led to). Conforms to Rule D9 and PRISM SRS non-causality mandates.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pytest

from backend.app.explain.alert import AlertExplainer, AlertSubject
from backend.app.explain.component import ComponentSubject, RiskComponentExplainer
from backend.app.explain.diversification import (
    DiversificationExplainer,
    DiversificationSubject,
)
from backend.app.explain.evidence import Evidence
from backend.app.explain.guardrails import validate_text
from backend.app.explain.schemas import ExplanationPayload
from backend.app.explain.score_change import ScoreChangeExplainer, ScoreChangeSubject
from backend.app.explain.shock import ShockExplainer, ShockSubject
from migrations.versions.c1d2e3f4a520_step_e3_sector_explain_config import (
    CONFIG as E3_CONFIG,
)
from migrations.versions.d2e3f4a5b621_step_e4_news_impact import (
    CONFIG as E4_CONFIG,
)
from migrations.versions.e3f4a5b6c722_step_e5_extended_explanations import (
    CONFIG as E5_CONFIG,
)
from migrations.versions.e3f4a5b6c722_step_e5_extended_explanations import (
    NEW_GLOSSARY_TERMS,
)
from migrations.versions.e7f8a9b0c116_step_e1_explanation_framework import (
    EXPLAIN_TEMPLATES as E1_CONFIG,
)
from migrations.versions.e7f8a9b0c116_step_e1_explanation_framework import (
    GLOSSARY as E1_GLOSSARY,
)
from migrations.versions.f8a9b0c1d217_step_e2_mst_explain_config import (
    CONFIG as E2_CONFIG,
)

BANNED_PHRASES: list[str] = [
    "buy",
    "sell",
    "hold",
    "target price",
    "price target",
    "guaranteed",
    "will rise",
    "will fall",
    "you should invest",
    "risk-free",
    "certain profit",
]

FORBIDDEN_CAUSAL_PHRASES: list[str] = [
    "because of",
    "caused by",
    "will cause",
    "led to",
]


def _check_text_safety(text: str, context: str) -> None:
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        pattern = rf"\b{re.escape(phrase.lower())}\b"
        if re.search(pattern, lowered):
            pytest.fail(f"Banned phrase '{phrase}' found in {context}: '{text}'")

    for causal_phrase in FORBIDDEN_CAUSAL_PHRASES:
        pattern = rf"\b{re.escape(causal_phrase.lower())}\b"
        if re.search(pattern, lowered):
            pytest.fail(f"Forbidden causal phrase '{causal_phrase}' found in {context}: '{text}'")


def _extract_strings(data: Any) -> list[str]:
    """Recursively collect all strings from a nested structure."""
    strings: list[str] = []
    if isinstance(data, str):
        strings.append(data)
    elif isinstance(data, dict):
        for key, val in data.items():
            if key in ("banned_phrases", "approval_note"):
                continue  # skip the list of banned phrases itself
            strings.extend(_extract_strings(val))
    elif isinstance(data, list):
        for item in data:
            strings.extend(_extract_strings(item))
    return strings


def test_wording_guard_scans_all_migration_templates() -> None:
    """Scan all template configs from migrations E1 to E5 for banned and causal wording."""
    configs = [
        ("E1_CONFIG", E1_CONFIG),
        ("E2_CONFIG", E2_CONFIG),
        ("E3_CONFIG", E3_CONFIG),
        ("E4_CONFIG", E4_CONFIG),
        ("E5_CONFIG", E5_CONFIG),
    ]

    for config_name, config in configs:
        strings = _extract_strings(config.get("templates", {}))
        for s in strings:
            _check_text_safety(s, f"{config_name} templates")


def test_wording_guard_scans_all_glossary_entries() -> None:
    """Scan all glossary entries from E1 and E5 for banned and causal wording."""
    all_glossary = list(E1_GLOSSARY) + list(NEW_GLOSSARY_TERMS)
    assert len(all_glossary) >= 14, "Glossary must have at least 14 terms"

    for term_key, label, plain_def, formula, _see_also in all_glossary:
        _check_text_safety(label, f"glossary label '{term_key}'")
        _check_text_safety(plain_def, f"glossary definition '{term_key}'")
        if formula:
            _check_text_safety(formula, f"glossary formula '{term_key}'")


def _collect_payload_texts(payload: ExplanationPayload) -> list[str]:
    texts = [payload.headline, payload.disclaimer]
    texts.extend(s.text for s in payload.summary_points)
    for section in payload.sections:
        texts.append(section.title)
        texts.extend(s.text for s in section.sentences)
    texts.extend(s.text for s in payload.confidence.reasons)
    texts.extend(payload.limitations)
    return texts


def test_wording_guard_scans_sample_generated_explanations() -> None:
    """Compose sample explanations for every subject type and assert all generated text is safe."""
    as_of = date(2026, 1, 15)

    from uuid import uuid4

    # 1. Shock explainer
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
            units="percent",
            source_table="shock_result",
            source_ref="INFY",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:sensitivity",
            kind="statistic",
            label="Sensitivity Beta",
            value=0.97,
            units="ratio",
            source_table="price_daily_adjusted",
            source_ref="beta",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:r_squared",
            kind="statistic",
            label="R-Squared",
            value=74.0,
            units="percent",
            source_table="price_daily_adjusted",
            source_ref="r2",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:weight",
            kind="statistic",
            label="Weight",
            value=12.5,
            units="percent",
            source_table="portfolio_holding",
            source_ref="wt",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:contribution",
            kind="statistic",
            label="Contribution",
            value=-0.61,
            units="percent",
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

    # 2. Diversification explainer
    port_id = uuid4()
    div_sub = DiversificationSubject(portfolio_id=port_id)
    ev_div = [
        Evidence(
            evidence_id="div:enb_entropy",
            kind="statistic",
            label="Entropy ENB",
            value=3.42,
            units="bets",
            source_table="portfolio_diversification_result",
            source_ref="enb:entropy",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:enb_eigen",
            kind="statistic",
            label="Eigen ENB",
            value=2.85,
            units="bets",
            source_table="portfolio_diversification_result",
            source_ref="enb:eigen",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:holding_count",
            kind="statistic",
            label="Holdings",
            value=8,
            units="count",
            source_table="portfolio_holding",
            source_ref="cnt",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:dominant_cluster",
            kind="config",
            label="Clusters",
            value="Cluster 1 (Banking & Financials)",
            source_table="portfolio_diversification_result",
            source_ref="dom",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:dominant_weight",
            kind="statistic",
            label="Cluster Weight",
            value=58.2,
            unit="percent",
            source_table="portfolio_diversification_result",
            source_ref="dom_wt",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:cluster_count",
            kind="statistic",
            label="Cluster Count",
            value=4,
            units="count",
            source_table="portfolio_diversification_result",
            source_ref="ccnt",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:cluster_hhi",
            kind="statistic",
            label="HHI",
            value=0.384,
            units="index",
            source_table="portfolio_diversification_result",
            source_ref="hhi",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:top_risk_assets",
            kind="statistic",
            label="Top Risk Assets",
            value="HDFCBANK (34.2%), ICICIBANK (24.0%)",
            units=None,
            source_table="portfolio_diversification_result",
            source_ref="top",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:formula_entropy",
            kind="rule",
            label="Formula",
            value="exp(-sum(p_i * ln(p_i))) with clamped percentage risk contributions p_i.",
            units=None,
            source_table="model_config",
            source_ref="f_ent",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="div:formula_eigen",
            kind="rule",
            label="Formula",
            value=(
                "(sum lambda_i)^2 / sum (lambda_i^2) across eigenvalues "
                "that describe how assets move together with each other."
            ),
            units=None,
            source_table="model_config",
            source_ref="f_eig",
            as_of=as_of,
        ),
    ]
    p_div = DiversificationExplainer().compose(ev_div, E5_CONFIG, "1.0.0", div_sub)

    # 3. Score Change explainer
    chg_sub = ScoreChangeSubject(symbol="TCS", as_of=as_of)
    ev_chg = [
        Evidence(
            evidence_id="change:current_score",
            kind="statistic",
            label="Current Score",
            value=62.4,
            units="points",
            source_table="stock_risk_result",
            source_ref="curr",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:previous_score",
            kind="statistic",
            label="Prev Score",
            value=55.1,
            units="points",
            source_table="stock_risk_result",
            source_ref="prev",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:score_delta",
            kind="statistic",
            label="Score Delta",
            value=7.3,
            units="points",
            source_table="stock_risk_result",
            source_ref="delta",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:dates",
            kind="rule",
            label="Dates",
            value="2026-01-08 to 2026-01-15",
            units=None,
            source_table="score_run",
            source_ref="dates",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:top1_driver",
            kind="statistic",
            label="Top Driver",
            value="30-Day Realized Volatility: +4.20 pts",
            units="points",
            source_table="score_component_value",
            source_ref="top1",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:top2_driver",
            kind="statistic",
            label="Second Driver",
            value="Sector Divergence Z-Score: +2.10 pts",
            units="points",
            source_table="score_component_value",
            source_ref="top2",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:top3_driver",
            kind="statistic",
            label="Third Driver",
            value="Maximum Drawdown: +1.00 pts",
            units="points",
            source_table="score_component_value",
            source_ref="top3",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:other_components",
            kind="statistic",
            label="Other",
            value="Remaining components contributed 0.00 pts",
            units="points",
            source_table="score_component_value",
            source_ref="other",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="change:methodology",
            kind="rule",
            label="Methodology",
            value="Decomposition partitions score shift into additive component points.",
            units=None,
            source_table="model_config",
            source_ref="meth",
            as_of=as_of,
        ),
    ]
    p_chg = ScoreChangeExplainer().compose(ev_chg, E5_CONFIG, "1.0.0", chg_sub)

    # 4. Alert explainer
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

    # 5. Risk Component explainer
    comp_sub = ComponentSubject(
        symbol="INFY",
        component_key="ewma_volatility",
    )
    ev_comp = [
        Evidence(
            evidence_id="raw",
            label="Raw value",
            kind="statistic",
            value=22.5,
            unit="percent",
            source_table="risk_component",
            source_ref="val",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="percentile",
            label="Percentile rank",
            kind="statistic",
            value=80.0,
            unit="percentile",
            source_table="risk_component",
            source_ref="pct",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="points",
            label="Risk points",
            kind="statistic",
            value=45.0,
            unit="points",
            source_table="risk_component",
            source_ref="pts",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="status",
            label="Status",
            kind="rule",
            value="ok",
            unit=None,
            source_table="risk_component",
            source_ref="stat",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="age",
            label="Data age",
            kind="statistic",
            value=0,
            unit="days",
            source_table="risk_component",
            source_ref="age",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="direction",
            label="Direction",
            kind="config",
            value="higher_is_riskier",
            unit=None,
            source_table="score_component_definition",
            source_ref="dir",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="weight",
            label="Component weight",
            kind="config",
            value=0.25,
            unit="share",
            source_table="score_component_definition",
            source_ref="wt",
            as_of=as_of,
        ),
        Evidence(
            evidence_id="label",
            label="Component label",
            kind="config",
            value="30-day EWMA Volatility",
            unit=None,
            source_table="score_component_definition",
            source_ref="lbl",
            as_of=as_of,
        ),
    ]
    p_comp = RiskComponentExplainer().compose(ev_comp, E1_CONFIG, "1.0.0", comp_sub)

    # Scan all generated payloads
    payloads = [p_shock, p_div, p_chg, p_alt, p_comp]
    for p in payloads:
        for text in _collect_payload_texts(p):
            _check_text_safety(text, f"generated payload for {p.subject.type}:{p.subject.key}")


def test_guardrails_fail_closed_on_prohibited_terms() -> None:
    """Ensure validate_text rejects banned investment phrases and causality."""
    cfg = {
        "banned_phrases": BANNED_PHRASES,
        "correlation_required_phrase": "moves together with",
    }

    # Banned advice terms
    with pytest.raises(ValueError, match="banned phrase: buy"):
        validate_text("We recommend to buy this asset.", cfg)

    with pytest.raises(ValueError, match="banned phrase: target price"):
        validate_text("The target price is 1500.", cfg)

    with pytest.raises(ValueError, match="banned phrase: guaranteed"):
        validate_text("This return is guaranteed.", cfg)

    with pytest.raises(ValueError, match="banned phrase: will rise"):
        validate_text("The stock will rise next week.", cfg)

    with pytest.raises(ValueError, match="banned phrase: you should invest"):
        validate_text("You should invest in IT.", cfg)

    # Missing correlation qualifier
    with pytest.raises(ValueError, match="moves together with"):
        validate_text("The correlation is high between these two assets.", cfg)

    # Safe correlation statement
    validate_text(
        "The asset moves together with the benchmark with correlation 0.72.",
        cfg,
    )


def test_forbidden_causal_phrases_detected() -> None:
    """Ensure _check_text_safety catches forbidden causal phrases."""
    for phrase in FORBIDDEN_CAUSAL_PHRASES:
        with pytest.raises(pytest.fail.Exception, match=f"Forbidden causal phrase '{phrase}'"):
            _check_text_safety(f"The return was {phrase} the market event.", "test context")

