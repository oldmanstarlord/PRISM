"""Step 12 coverage contract for the eight required risk dimensions."""

from __future__ import annotations

from dataclasses import dataclass

REQUIRED_DIMENSIONS: tuple[str, ...] = (
    "market",
    "liquidity",
    "structure",
    "relative",
    "fundamentals",
    "governance",
    "events",
    "macro",
)


@dataclass(frozen=True)
class DimensionCoverage:
    active_components: tuple[str, ...]
    unavailable_reason: str | None = None


COVERAGE_MATRIX: dict[str, DimensionCoverage] = {
    "market": DimensionCoverage(
        ("ewma_volatility", "beta_to_benchmark", "max_drawdown_1y", "tail_loss")
    ),
    "liquidity": DimensionCoverage(("avg_traded_value", "zero_volume_days")),
    "structure": DimensionCoverage(("mst_centrality",)),
    "relative": DimensionCoverage(("sector_divergence",)),
    "fundamentals": DimensionCoverage(
        ("fund_leverage", "fund_coverage", "fund_profit_trend", "fund_cashflow_quality")
    ),
    "governance": DimensionCoverage(
        (
            "gov_promoter_pledge",
            "gov_promoter_holding_change",
            "gov_institutional_flow",
            "gov_insider_activity",
        ),
        "No verified production governance source is loaded; components return missing.",
    ),
    "events": DimensionCoverage(
        ("event_risk_pressure",),
        "No approved live announcement feed is configured; the component returns missing.",
    ),
    "macro": DimensionCoverage(
        ("macro_exposure", "news_policy_pressure"),
        "India 10Y and FII/DII sources are TBD; coverage is partial when absent.",
    ),
}


def validate_coverage_matrix() -> list[str]:
    """Return contract violations; an empty list means all dimensions are explicit."""
    violations: list[str] = []
    if set(COVERAGE_MATRIX) != set(REQUIRED_DIMENSIONS):
        missing = sorted(set(REQUIRED_DIMENSIONS) - set(COVERAGE_MATRIX))
        extra = sorted(set(COVERAGE_MATRIX) - set(REQUIRED_DIMENSIONS))
        violations.append(f"dimension mismatch: missing={missing}, extra={extra}")
    for dimension, entry in COVERAGE_MATRIX.items():
        if not entry.active_components and not entry.unavailable_reason:
            violations.append(f"{dimension} silently has neither components nor unavailable reason")
    return violations
