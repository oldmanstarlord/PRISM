"""Portfolio-level synthesis of holding risk and structural concentration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HoldingScoreInput:
    symbol: str
    weight: float
    risk_score: float
    confidence: float


@dataclass(frozen=True)
class PortfolioScoreResult:
    total_score: float
    holding_risk_score: float
    structure_score: float | None
    structure_components: dict[str, float | None]
    confidence: float
    weighted_holding_confidence: float
    weakest_large_holding_confidence: float | None
    coverage: float
    status: str
    contributions: list[dict[str, Any]]


def compute_portfolio_score(
    holdings: list[HoldingScoreInput],
    *,
    enb_risk_entropy: float | None,
    maximum_cluster_weight: float | None,
    config: dict[str, Any],
) -> PortfolioScoreResult:
    """Compute a transparent portfolio score without persisting or fetching data."""
    if not holdings:
        raise ValueError("At least one scored holding is required")

    raw_weight = sum(max(0.0, holding.weight) for holding in holdings)
    if raw_weight <= 0:
        raise ValueError("Scored holding weights must sum to a positive value")

    normalized = [
        HoldingScoreInput(
            symbol=holding.symbol,
            weight=max(0.0, holding.weight) / raw_weight,
            risk_score=holding.risk_score,
            confidence=holding.confidence,
        )
        for holding in holdings
    ]
    holding_risk = sum(holding.weight * holding.risk_score for holding in normalized)
    weighted_confidence = sum(holding.weight * holding.confidence for holding in normalized)

    large_threshold = float(config.get("large_holding_weight_threshold", 0.10))
    large_confidences = [
        holding.confidence for holding in normalized if holding.weight >= large_threshold
    ]
    weakest_large = min(large_confidences) if large_confidences else None
    confidence = min(weighted_confidence, weakest_large or weighted_confidence)

    structure_score: float | None = None
    concentration_risk: float | None = None
    effective_bet_risk: float | None = None
    if enb_risk_entropy is not None and maximum_cluster_weight is not None:
        number_of_holdings = len(normalized)
        effective_bet_risk = 100.0 * (
            1.0 - min(1.0, max(0.0, enb_risk_entropy) / number_of_holdings)
        )
        concentration_risk = 100.0 * min(1.0, max(0.0, maximum_cluster_weight))
        structure_weights = config.get(
            "portfolio_structure_weights",
            {"cluster_concentration": 0.50, "effective_bets": 0.50},
        )
        cluster_weight = float(structure_weights.get("cluster_concentration", 0.50))
        effective_bets_weight = float(structure_weights.get("effective_bets", 0.50))
        structure_total = cluster_weight + effective_bets_weight
        if structure_total <= 0:
            raise ValueError("Portfolio structure weights must sum to a positive value")
        structure_score = (
            cluster_weight * concentration_risk + effective_bets_weight * effective_bet_risk
        ) / structure_total

    score_weights = config.get(
        "portfolio_score_weights", {"holding_risk": 0.80, "structure": 0.20}
    )
    holding_weight = float(score_weights.get("holding_risk", 0.80))
    structure_weight = float(score_weights.get("structure", 0.20))
    possible_weight = holding_weight + structure_weight
    available_weight = holding_weight + (structure_weight if structure_score is not None else 0.0)
    if possible_weight <= 0 or available_weight <= 0:
        raise ValueError("Portfolio score weights must sum to a positive value")

    weighted_score = holding_weight * holding_risk
    if structure_score is not None:
        weighted_score += structure_weight * structure_score
    total_score = weighted_score / available_weight
    coverage = available_weight / possible_weight
    confidence *= coverage

    contributions = [
        {
            "symbol": holding.symbol,
            "weight": round(holding.weight, 6),
            "risk_score": round(holding.risk_score, 2),
            "confidence": round(holding.confidence, 2),
            "weighted_risk_points": round(holding.weight * holding.risk_score, 2),
        }
        for holding in normalized
    ]

    return PortfolioScoreResult(
        total_score=round(total_score, 2),
        holding_risk_score=round(holding_risk, 2),
        structure_score=round(structure_score, 2) if structure_score is not None else None,
        structure_components={
            "cluster_concentration": (
                round(concentration_risk, 2) if concentration_risk is not None else None
            ),
            "effective_bets": (
                round(effective_bet_risk, 2) if effective_bet_risk is not None else None
            ),
        },
        confidence=round(confidence, 2),
        weighted_holding_confidence=round(weighted_confidence, 2),
        weakest_large_holding_confidence=(
            round(weakest_large, 2) if weakest_large is not None else None
        ),
        coverage=round(coverage, 4),
        status="ok" if structure_score is not None else "partial",
        contributions=contributions,
    )
