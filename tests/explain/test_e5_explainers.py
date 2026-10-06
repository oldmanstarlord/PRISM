"""Step E5 test suite: new explainers, guardrails, glossary, and fingerprint caching."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.explain.diversification import (
    DiversificationExplainer,
    DiversificationSubject,
)
from backend.app.explain.evidence import Evidence
from backend.app.explain.guardrails import apply_payload_guardrails, validate_text
from backend.app.explain.score_change import (
    ScoreChangeExplainer,
    ScoreChangeSubject,
)
from backend.app.explain.service import _fingerprint
from backend.app.explain.shock import (
    ShockExplainer,
    ShockSubject,
)
from backend.app.main import app

client = TestClient(app)

BASE_CONFIG = {
    "disclaimer": (
        "PRISM risk metrics are statistical summaries, not financial forecasts "
        "or investment advice."
    ),
    "correlation_required_phrase": "moves together with",
    "banned_phrases": ["guaranteed", "risk-free", "certain profit"],
    "limitations": [
        "Statistical estimates are historical and subject to parameter uncertainty.",
    ],
}


def test_shock_explainer_compose_and_guardrails() -> None:
    explainer = ShockExplainer()
    assert explainer.subject_type == "shock"

    as_of = date(2026, 9, 30)
    subject = ShockSubject(
        holding_symbol="INFY",
        shocked_symbol="NIFTY",
        shock_pct=-5.0,
        method="regression_beta",
    )
    assert "NIFTY->INFY" in subject.key

    evidence = [
        Evidence(
            evidence_id="shock:impact",
            kind="statistic",
            label="Predicted Scenario Price Move",
            value=-4.85,
            unit="percentage",
            source_table="shock_result",
            source_ref="holding:INFY",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:sensitivity",
            kind="statistic",
            label="Statistical Sensitivity (Beta)",
            value=0.97,
            unit="ratio",
            source_table="price_daily_adjusted",
            source_ref="beta:INFY",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:r_squared",
            kind="statistic",
            label="R-Squared Co-Movement",
            value=74.0,
            unit="percentage",
            source_table="price_daily_adjusted",
            source_ref="r2:INFY",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:weight",
            kind="statistic",
            label="Holding Capital Weight",
            value=12.5,
            unit="percentage",
            source_table="portfolio_holding",
            source_ref="weight:INFY",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:contribution",
            kind="statistic",
            label="Portfolio Loss Contribution",
            value=-0.61,
            unit="percentage",
            source_table="shock_result",
            source_ref="contrib:INFY",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:path",
            kind="rule",
            label="Transmission Path",
            value="Direct equity market index exposure moves together with empirical market beta",
            source_table="shock_scenario",
            source_ref="path:INFY",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:assumption:linear",
            kind="config",
            label="Assumption: Linear Co-Movement",
            value="Asset sensitivity estimated over trailing 126 days is assumed constant.",
            source_table="model_config",
            source_ref="shock_simulator",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:assumption:liquidity",
            kind="config",
            label="Assumption: No Liquidity Feedback",
            value="Prices adjust without order-book slippage or liquidation cascades.",
            source_table="model_config",
            source_ref="shock_simulator",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:assumption:stability",
            kind="config",
            label="Assumption: Covariance Stability",
            value="Historical dependence structure holds during hypothetical shock scenario.",
            source_table="model_config",
            source_ref="shock_simulator",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="shock:assumption:isolated",
            kind="config",
            label="Assumption: Isolated Exogenous Shock",
            value=(
                "Hypothetical stress is isolated to NIFTY without independent "
                "contemporaneous shocks."
            ),
            source_table="model_config",
            source_ref="shock_simulator",
            as_of=as_of,
            data_age_days=0,
        ),
    ]

    payload = explainer.compose(evidence, BASE_CONFIG, "1.0.0", subject)
    guarded = apply_payload_guardrails(payload, BASE_CONFIG)

    assert guarded.subject.type == "shock"
    assert len(guarded.sections) >= 2

    # Verify non-causal language and absence of investment advice (Rule D9)
    for section in guarded.sections:
        for sentence in section.sentences:
            validate_text(sentence.text, BASE_CONFIG)
            assert "will cause" not in sentence.text.lower()
            assert "buy" not in sentence.text.lower()
            assert "sell" not in sentence.text.lower()

    for sentence in guarded.summary_points:
        validate_text(sentence.text, BASE_CONFIG)

    summary_text = " ".join(s.text for s in guarded.summary_points)
    assert "INFY" in summary_text
    assert "0.97" in summary_text
    assert "74" in summary_text


def test_diversification_explainer_compose_and_guardrails() -> None:
    explainer = DiversificationExplainer()
    assert explainer.subject_type == "diversification"

    portfolio_id = uuid4()
    as_of = date(2026, 9, 30)
    subject = DiversificationSubject(portfolio_id=portfolio_id)
    assert subject.key == f"portfolio:{portfolio_id}"

    evidence = [
        Evidence(
            evidence_id="div:enb_entropy",
            kind="statistic",
            label="Risk-Contribution Entropy ENB",
            value=3.42,
            unit="bets",
            source_table="portfolio_diversification_result",
            source_ref="enb:entropy",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:enb_eigen",
            kind="statistic",
            label="Eigenvalue Decomposition ENB",
            value=2.85,
            unit="bets",
            source_table="portfolio_diversification_result",
            source_ref="enb:eigen",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:holding_count",
            kind="statistic",
            label="Total Portfolio Holdings",
            value=8,
            source_table="portfolio_holdings",
            source_ref="count",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:dominant_cluster",
            kind="config",
            label="Dominant MST Cluster",
            value="Cluster 1 (Banking & Financials)",
            source_table="mst_clusters",
            source_ref="cluster:1",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:dominant_weight",
            kind="statistic",
            label="Dominant Cluster Weight",
            value=58.2,
            unit="percentage",
            source_table="portfolio_diversification_result",
            source_ref="cluster_weight:1",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:cluster_count",
            kind="statistic",
            label="Distinct Clusters Represented",
            value=4,
            unit="count",
            source_table="portfolio_diversification_result",
            source_ref="clusters:count",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:cluster_hhi",
            kind="statistic",
            label="Cluster Weight HHI",
            value=0.384,
            unit="index",
            source_table="portfolio_diversification_result",
            source_ref="cluster:hhi",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:top_risk_assets",
            kind="statistic",
            label="Top Risk Contributors",
            value="HDFCBANK (34.2%), ICICIBANK (24.0%)",
            unit=None,
            source_table="portfolio_diversification_result",
            source_ref="top_assets",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:formula_entropy",
            kind="rule",
            label="Entropy Calculation Formula",
            value="exp(-sum(p_i * ln(p_i))) with clamped percentage risk contributions p_i.",
            unit=None,
            source_table="model_config",
            source_ref="portfolio_diversification",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="div:formula_eigen",
            kind="rule",
            label="Eigenvalue Calculation Formula",
            value=(
                "(sum lambda_i)^2 / sum (lambda_i^2) across eigenvalues that "
                "describe how assets move together with each other."
            ),
            unit=None,
            source_table="model_config",
            source_ref="portfolio_diversification",
            as_of=as_of,
            data_age_days=0,
        ),
    ]

    payload = explainer.compose(evidence, BASE_CONFIG, "1.0.0", subject)
    guarded = apply_payload_guardrails(payload, BASE_CONFIG)

    assert guarded.subject.type == "diversification"
    assert len(guarded.sections) >= 2

    for section in guarded.sections:
        for sentence in section.sentences:
            validate_text(sentence.text, BASE_CONFIG)

    for sentence in guarded.summary_points:
        validate_text(sentence.text, BASE_CONFIG)

    summary_text = " ".join(s.text for s in guarded.summary_points)
    assert "3.42" in summary_text
    assert "Cluster 1" in summary_text


def test_score_change_explainer_compose_and_guardrails() -> None:
    explainer = ScoreChangeExplainer()
    assert explainer.subject_type == "score_change"

    as_of = date(2026, 9, 30)
    subject = ScoreChangeSubject(symbol="TCS", as_of=as_of)
    assert subject.key == f"TCS:{as_of.isoformat()}"

    evidence = [
        Evidence(
            evidence_id="change:current_score",
            kind="statistic",
            label="Current Total Risk Score",
            value=62.4,
            unit="points",
            source_table="stock_risk_result",
            source_ref="score:latest",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="change:previous_score",
            kind="statistic",
            label="Previous Total Risk Score",
            value=55.1,
            unit="points",
            source_table="stock_risk_result",
            source_ref="score:prev",
            as_of=as_of,
            data_age_days=7,
        ),
        Evidence(
            evidence_id="change:score_delta",
            kind="statistic",
            label="Net Score Change",
            value=7.3,
            unit="points",
            source_table="stock_risk_result",
            source_ref="score:delta",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="change:dates",
            kind="rule",
            label="Evaluation Period Dates",
            value="2026-09-23 to 2026-09-30",
            unit=None,
            source_table="score_run",
            source_ref="run:latest",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="change:top1_driver",
            kind="statistic",
            label="Primary Driver (30-Day Volatility)",
            value="30-Day Realized Volatility: +4.20 pts (pct rank +12.5)",
            unit="points",
            source_table="score_component_value",
            source_ref="comp:vol_30d",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="change:top2_driver",
            kind="statistic",
            label="Secondary Driver (Sector Divergence)",
            value="Sector Divergence: +2.10 pts",
            unit="points",
            source_table="score_component_value",
            source_ref="comp:sec_div",
            as_of=as_of,
            data_age_days=0,
        ),
        Evidence(
            evidence_id="change:top3_driver",
            kind="statistic",
            label="Tertiary Driver (Promoter Pledge)",
            value="Promoter Pledge: +1.00 pts",
            unit="points",
            source_table="score_component_value",
            source_ref="comp:pledge",
            as_of=as_of,
            data_age_days=0,
        ),
    ]

    payload = explainer.compose(evidence, BASE_CONFIG, "1.0.0", subject)
    guarded = apply_payload_guardrails(payload, BASE_CONFIG)

    assert guarded.subject.type == "score_change"
    assert len(guarded.sections) >= 1
    assert len(guarded.summary_points) >= 2

    for section in guarded.sections:
        for sentence in section.sentences:
            validate_text(sentence.text, BASE_CONFIG)

    full_text = " ".join(
        sentence.text for section in guarded.sections for sentence in section.sentences
    )
    assert "TCS" in guarded.headline
    assert "7.3" in guarded.headline
    assert "Sector Divergence" in full_text


def test_fingerprint_is_deterministic() -> None:
    data_1 = {
        "subject": "INFY:latest",
        "as_of": "2026-09-30",
        "config_fingerprint": "abc123hash",
        "evidence": [{"id": "ev1", "value": 1.23}],
    }
    data_2 = {
        "subject": "INFY:latest",
        "as_of": "2026-09-30",
        "config_fingerprint": "abc123hash",
        "evidence": [{"id": "ev1", "value": 1.23}],
    }
    data_different = {
        "subject": "INFY:latest",
        "as_of": "2026-09-30",
        "config_fingerprint": "abc123hash",
        "evidence": [{"id": "ev1", "value": 1.24}],
    }

    fp1 = _fingerprint(data_1)
    fp2 = _fingerprint(data_2)
    fp3 = _fingerprint(data_different)

    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 64


def test_glossary_endpoints() -> None:
    resp = client.get("/api/v1/glossary")
    assert resp.status_code == 200
    glossary = resp.json()
    keys = [item["term_key"] for item in glossary]
    assert "effective_number_of_bets" in keys
    assert "mst_path_decay" in keys
    assert "beta" in keys
    assert "r_squared" in keys
    assert "score_change" in keys

    resp_term = client.get("/api/v1/glossary/effective_number_of_bets")
    assert resp_term.status_code == 200
    term_data = resp_term.json()
    assert term_data["term_key"] == "effective_number_of_bets"
    assert "plain_definition" in term_data

    resp_404 = client.get("/api/v1/glossary/nonexistent_term_xyz")
    assert resp_404.status_code == 404


def test_explain_search_and_recent_endpoints() -> None:
    resp_recent = client.get("/api/v1/explain/recent?limit=5")
    assert resp_recent.status_code == 200
    assert isinstance(resp_recent.json(), list)

    resp_search = client.get("/api/v1/explain/search?q=INFY")
    assert resp_search.status_code == 200
    assert isinstance(resp_search.json(), list)

    resp_search_empty = client.get("/api/v1/explain/search?q=")
    assert resp_search_empty.status_code == 422
