"""Performance budget test suite for PRISM explanations (Step E6).

Verifies compliance with E5 latency budgets:
- Precomputed explanation fetch / cache lookup: under 1.0s.
- On-demand explanation compose and guardrail verification: under 3.0s.
- In-memory composition latency: under 50ms.
"""

from __future__ import annotations

import time
from datetime import date
from uuid import uuid4

from backend.app.explain.diversification import DiversificationExplainer, DiversificationSubject
from backend.app.explain.evidence import Evidence
from backend.app.explain.guardrails import apply_payload_guardrails
from backend.app.explain.schemas import ExplanationPayload
from backend.app.explain.shock import ShockExplainer, ShockSubject
from migrations.versions.e3f4a5b6c722_step_e5_extended_explanations import (
    CONFIG as E5_CONFIG,
)

PRECOMPUTED_BUDGET_SECONDS = 1.0
ON_DEMAND_BUDGET_SECONDS = 3.0
IN_MEMORY_COMPOSE_BUDGET_SECONDS = 0.050  # 50 ms


def test_in_memory_compose_budget_shock() -> None:
    """Assert ShockExplainer compose runs in under 50ms."""
    as_of = date(2026, 1, 15)
    sub = ShockSubject(
        holding_symbol="INFY",
        shocked_symbol="NIFTY",
        shock_pct=-5.0,
        method="regression_beta",
    )
    ev = [
        Evidence(
            evidence_id="shock:impact", kind="statistic", label="Move",
            value=-4.85, source_table="shock", source_ref="1", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:sensitivity", kind="statistic", label="Beta",
            value=0.97, source_table="shock", source_ref="2", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:r_squared", kind="statistic", label="R2",
            value=74.0, source_table="shock", source_ref="3", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:weight", kind="statistic", label="Wt",
            value=12.5, source_table="shock", source_ref="4", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:contribution", kind="statistic", label="Contrib",
            value=-0.61, source_table="shock", source_ref="5", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:path", kind="rule", label="Path",
            value="Market beta moves together with index",
            source_table="shock", source_ref="6", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:linear", kind="config", label="Linear",
            value="Constant", source_table="shock", source_ref="7", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:liquidity", kind="config", label="Liquidity",
            value="No slippage", source_table="shock", source_ref="8", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:stability", kind="config", label="Stability",
            value="Stable", source_table="shock", source_ref="9", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:isolated", kind="config", label="Isolated",
            value="Isolated", source_table="shock", source_ref="10", as_of=as_of,
        ),
    ]

    explainer = ShockExplainer()
    start = time.perf_counter()
    payload = explainer.compose(ev, E5_CONFIG, "1.0.0", sub)
    guarded = apply_payload_guardrails(payload, E5_CONFIG)
    elapsed = time.perf_counter() - start

    assert guarded is not None
    assert elapsed < IN_MEMORY_COMPOSE_BUDGET_SECONDS, (
        f"Shock compose took {elapsed:.4f}s, budget is {IN_MEMORY_COMPOSE_BUDGET_SECONDS}s"
    )


def test_in_memory_compose_budget_diversification() -> None:
    """Assert DiversificationExplainer compose runs in under 50ms."""
    as_of = date(2026, 1, 15)
    sub = DiversificationSubject(portfolio_id=uuid4())
    ev = [
        Evidence(
            evidence_id="div:enb_entropy", kind="statistic", label="Entropy",
            value=3.42, source_table="div", source_ref="1", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:enb_eigen", kind="statistic", label="Eigen",
            value=2.85, source_table="div", source_ref="2", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:holding_count", kind="statistic", label="Holdings",
            value=8, source_table="div", source_ref="3", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:dominant_cluster", kind="config", label="Cluster",
            value="Cluster 1", source_table="div", source_ref="4", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:dominant_weight", kind="statistic", label="Weight",
            value=58.2, source_table="div", source_ref="5", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:cluster_count", kind="statistic", label="Count",
            value=4, source_table="div", source_ref="6", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:cluster_hhi", kind="statistic", label="HHI",
            value=0.384, source_table="div", source_ref="7", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:top_risk_assets", kind="statistic", label="Top",
            value="HDFCBANK (34.2%)", source_table="div", source_ref="8", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:formula_entropy", kind="rule", label="F1",
            value="exp(-sum(p*ln(p)))", source_table="div", source_ref="9", as_of=as_of,
        ),
        Evidence(
            evidence_id="div:formula_eigen", kind="rule", label="F2",
            value="sum lambda moves together with each other",
            source_table="div", source_ref="10", as_of=as_of,
        ),
    ]

    explainer = DiversificationExplainer()
    start = time.perf_counter()
    payload = explainer.compose(ev, E5_CONFIG, "1.0.0", sub)
    guarded = apply_payload_guardrails(payload, E5_CONFIG)
    elapsed = time.perf_counter() - start

    assert guarded is not None
    assert elapsed < IN_MEMORY_COMPOSE_BUDGET_SECONDS, (
        f"Diversification compose took {elapsed:.4f}s, budget={IN_MEMORY_COMPOSE_BUDGET_SECONDS}s"
    )


def test_on_demand_budget_aggregate() -> None:
    """Assert generating 20 on-demand explanations back-to-back stays under the 3.0s budget."""
    as_of = date(2026, 1, 15)
    sub = ShockSubject(
        holding_symbol="INFY",
        shocked_symbol="NIFTY",
        shock_pct=-5.0,
        method="regression_beta",
    )
    ev = [
        Evidence(
            evidence_id="shock:impact", kind="statistic", label="Move",
            value=-4.85, source_table="shock", source_ref="1", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:sensitivity", kind="statistic", label="Beta",
            value=0.97, source_table="shock", source_ref="2", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:r_squared", kind="statistic", label="R2",
            value=74.0, source_table="shock", source_ref="3", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:weight", kind="statistic", label="Wt",
            value=12.5, source_table="shock", source_ref="4", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:contribution", kind="statistic", label="Contrib",
            value=-0.61, source_table="shock", source_ref="5", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:path", kind="rule", label="Path",
            value="Market beta moves together with index",
            source_table="shock", source_ref="6", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:linear", kind="config", label="Linear",
            value="Constant", source_table="shock", source_ref="7", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:liquidity", kind="config", label="Liquidity",
            value="No slippage", source_table="shock", source_ref="8", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:stability", kind="config", label="Stability",
            value="Stable", source_table="shock", source_ref="9", as_of=as_of,
        ),
        Evidence(
            evidence_id="shock:assumption:isolated", kind="config", label="Isolated",
            value="Isolated", source_table="shock", source_ref="10", as_of=as_of,
        ),
    ]

    explainer = ShockExplainer()
    start = time.perf_counter()
    for _ in range(20):
        p = explainer.compose(ev, E5_CONFIG, "1.0.0", sub)
        _ = apply_payload_guardrails(p, E5_CONFIG)
    total_time = time.perf_counter() - start

    assert total_time < ON_DEMAND_BUDGET_SECONDS, (
        f"20 on-demand runs took {total_time:.4f}s, budget is {ON_DEMAND_BUDGET_SECONDS}s"
    )


def test_precomputed_lookup_simulation_budget() -> None:
    """Assert simulated precomputed cached payload lookup is under 1.0s budget."""
    from tests.explain.test_golden_explanations import GOLDEN_DIR

    golden_file = GOLDEN_DIR / "INFY.json"
    start = time.perf_counter()
    raw = golden_file.read_text(encoding="utf-8")
    payload = ExplanationPayload.model_validate_json(raw)
    assert len(payload.evidence) > 0
    elapsed = time.perf_counter() - start

    assert elapsed < PRECOMPUTED_BUDGET_SECONDS, (
        f"Precomputed fetch took {elapsed:.4f}s, budget is {PRECOMPUTED_BUDGET_SECONDS}s"
    )
