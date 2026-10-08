"""Pure portfolio-risk, diversification, MST and stress calculations."""

from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from numpy.typing import NDArray

from backend.app.portfolio_analytics.schemas import (
    ConcentrationSummary,
    DiversificationSummary,
    HoldingAnalytics,
    IndustryWeight,
    MstBridgeSummary,
    MstClusterSummary,
    MstEdgeSummary,
    MstPathSummary,
    MstPortfolioSummary,
    MstStabilitySummary,
    PerformancePoint,
    PerformanceSummary,
    StressHoldingResult,
    StressScenarioInput,
    StressScenarioResult,
)

ANNUALISATION_FACTOR = 252
MST_CLUSTER_CORRELATION_FLOOR = 0.50
MST_STABILITY_HIGH_THRESHOLD = 0.80
MST_STABILITY_MODERATE_THRESHOLD = 0.60
MST_STABILITY_WINDOW_COUNT = 5


@dataclass(frozen=True, slots=True)
class MstEdgeData:
    symbol_a: str
    symbol_b: str
    correlation: float
    distance: float


def _edge_key(symbol_a: str, symbol_b: str) -> tuple[str, str]:
    return min(symbol_a, symbol_b), max(symbol_a, symbol_b)


def _stability_confidence(
    value: float | None,
) -> Literal["unavailable", "low", "moderate", "high"]:
    if value is None:
        return "unavailable"
    if value >= MST_STABILITY_HIGH_THRESHOLD:
        return "high"
    if value >= MST_STABILITY_MODERATE_THRESHOLD:
        return "moderate"
    return "low"


def calculate_mst_stability(
    windows: list[tuple[date, list[MstEdgeData]]],
) -> tuple[MstStabilitySummary, dict[tuple[str, str], float | None]]:
    """Measure current-edge persistence and adjacent-window overlap deterministically."""
    if not windows:
        raise ValueError("At least the current MST window is required")
    bounded_windows = windows[:MST_STABILITY_WINDOW_COUNT]
    edge_sets = [
        {_edge_key(edge.symbol_a, edge.symbol_b) for edge in edges}
        for _window_end, edges in bounded_windows
    ]
    current_edges = edge_sets[0]
    persistence: dict[tuple[str, str], float | None]
    if len(edge_sets) < 2:
        persistence = {edge: None for edge in current_edges}
        return (
            MstStabilitySummary(
                method=(
                    "current-edge frequency and mean adjacent-window edge overlap across up to "
                    f"{MST_STABILITY_WINDOW_COUNT} compatible completed MST runs"
                ),
                runs_compared=1,
                window_ends=[bounded_windows[0][0]],
                consecutive_edge_overlap=None,
                current_edge_persistence=None,
                confidence="unavailable",
                reason="At least two compatible completed MST runs are required.",
            ),
            persistence,
        )

    run_count = len(edge_sets)
    persistence = {
        edge: round(sum(edge in edge_set for edge_set in edge_sets) / run_count, 8)
        for edge in sorted(current_edges)
    }
    overlaps: list[float] = []
    for newer, older in zip(edge_sets, edge_sets[1:], strict=False):
        denominator = max(len(newer), len(older), 1)
        overlaps.append(len(newer & older) / denominator)
    current_persistence = (
        float(np.mean(list(persistence.values()))) if persistence else 1.0
    )
    consecutive_overlap = float(np.mean(overlaps))
    confidence = _stability_confidence(current_persistence)
    return (
        MstStabilitySummary(
            method=(
                "current-edge frequency and mean adjacent-window edge overlap across up to "
                f"{MST_STABILITY_WINDOW_COUNT} compatible completed MST runs"
            ),
            runs_compared=run_count,
            window_ends=[window_end for window_end, _edges in bounded_windows],
            consecutive_edge_overlap=round(consecutive_overlap, 8),
            current_edge_persistence=round(current_persistence, 8),
            confidence=confidence,
            reason=(
                f"Mean current-edge persistence is {current_persistence:.1%}; thresholds are "
                f"{MST_STABILITY_MODERATE_THRESHOLD:.0%} for moderate and "
                f"{MST_STABILITY_HIGH_THRESHOLD:.0%} for high confidence."
            ),
        ),
        persistence,
    )


@dataclass(frozen=True, slots=True)
class RiskCalculation:
    performance: PerformanceSummary
    holdings: list[HoldingAnalytics]
    concentration: ConcentrationSummary
    diversification: DiversificationSummary
    returns: pd.DataFrame
    covariance_daily: NDArray[np.float64]


def _trade_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def calculate_risk(
    prices: pd.DataFrame,
    weights_by_symbol: dict[str, float],
    industries: dict[str, str],
    divergence: dict[str, tuple[float, str]],
) -> RiskCalculation:
    """Calculate constant-weight daily portfolio history and covariance risk metrics."""
    symbols = list(weights_by_symbol)
    weights = np.asarray([weights_by_symbol[symbol] for symbol in symbols], dtype=np.float64)
    ordered_prices = prices.loc[:, symbols]
    returns = np.log(ordered_prices / ordered_prices.shift(1)).iloc[1:]
    if len(returns) < 2:
        raise ValueError("At least two common return observations are required")

    return_values = returns.to_numpy(dtype=np.float64)
    portfolio_returns = return_values @ weights
    wealth_after_returns = np.exp(np.cumsum(portfolio_returns))
    wealth = np.concatenate((np.asarray([1.0]), wealth_after_returns))
    running_peak = np.maximum.accumulate(wealth)
    drawdown = wealth / running_peak - 1.0
    points = [
        PerformancePoint(
            trade_date=_trade_date(index_value),
            portfolio_index=round(float(index_level * 100.0), 4),
            drawdown=round(float(drawdown_value), 6),
        )
        for index_value, index_level, drawdown_value in zip(
            ordered_prices.index, wealth, drawdown, strict=True
        )
    ]

    daily_volatility = float(np.std(portfolio_returns, ddof=1))
    negative_returns = np.minimum(portfolio_returns, 0.0)
    downside_daily = float(np.sqrt(np.mean(np.square(negative_returns))))
    performance = PerformanceSummary(
        total_return=round(float(wealth[-1] - 1.0), 8),
        annualized_return=round(float(np.exp(np.mean(portfolio_returns) * 252.0) - 1.0), 8),
        annualized_volatility=round(daily_volatility * math.sqrt(252.0), 8),
        downside_volatility=round(downside_daily * math.sqrt(252.0), 8),
        max_drawdown=round(abs(float(np.min(drawdown))), 8),
        points=points,
    )

    covariance_daily_raw = np.cov(return_values, rowvar=False, ddof=1)
    if len(symbols) == 1:
        covariance_daily = np.asarray([[float(covariance_daily_raw)]], dtype=np.float64)
    else:
        covariance_daily = np.asarray(covariance_daily_raw, dtype=np.float64)
    covariance_annual = covariance_daily * ANNUALISATION_FACTOR
    sigma_weights = covariance_annual @ weights
    portfolio_variance = float(weights @ sigma_weights)
    portfolio_volatility = math.sqrt(max(portfolio_variance, 0.0))
    holding_volatilities = np.sqrt(np.maximum(np.diag(covariance_annual), 0.0))

    holdings: list[HoldingAnalytics] = []
    for index, symbol in enumerate(symbols):
        if portfolio_volatility > 1e-12 and portfolio_variance > 1e-12:
            marginal_risk = float(sigma_weights[index] / portfolio_volatility)
            risk_contribution = float(weights[index] * sigma_weights[index] / portfolio_variance)
        else:
            marginal_risk = 0.0
            risk_contribution = 0.0
        score = divergence.get(symbol)
        holdings.append(
            HoldingAnalytics(
                symbol=symbol,
                industry=industries[symbol],
                weight=float(weights[index]),
                annualized_volatility=round(float(holding_volatilities[index]), 8),
                marginal_risk=round(marginal_risk, 8),
                risk_contribution=round(risk_contribution, 8),
                divergence_20d=round(score[0], 8) if score else None,
                divergence_band=score[1] if score else None,
            )
        )

    industry_weights: dict[str, float] = {}
    for symbol, weight in weights_by_symbol.items():
        industry = industries[symbol]
        industry_weights[industry] = industry_weights.get(industry, 0.0) + weight
    ordered_industries = sorted(industry_weights.items(), key=lambda item: (-item[1], item[0]))
    holding_hhi = float(np.sum(np.square(weights)))
    industry_hhi = float(sum(weight * weight for weight in industry_weights.values()))
    largest_symbol = max(symbols, key=lambda symbol: weights_by_symbol[symbol])
    concentration = ConcentrationSummary(
        holding_hhi=round(holding_hhi, 8),
        effective_holdings=round(1.0 / holding_hhi, 4),
        largest_holding_symbol=largest_symbol,
        largest_holding_weight=round(weights_by_symbol[largest_symbol], 8),
        industry_hhi=round(industry_hhi, 8),
        effective_industries=round(1.0 / industry_hhi, 4),
        industry_weights=[
            IndustryWeight(industry=industry, weight=round(weight, 8))
            for industry, weight in ordered_industries
        ],
    )

    risk_contributions = np.asarray(
        [max(holding.risk_contribution, 0.0) for holding in holdings], dtype=np.float64
    )
    positive_total = float(np.sum(risk_contributions))
    if positive_total > 1e-12:
        probabilities = risk_contributions / positive_total
        positive = probabilities[probabilities > 1e-12]
        risk_enb = float(np.exp(-np.sum(positive * np.log(positive))))
    else:
        risk_enb = 1.0
    correlation = returns.corr().to_numpy(dtype=np.float64)
    eigenvalues = np.maximum(np.linalg.eigvalsh((correlation + correlation.T) / 2.0), 0.0)
    eigen_square_sum = float(np.sum(np.square(eigenvalues)))
    correlation_enb = (
        float(np.sum(eigenvalues) ** 2 / eigen_square_sum)
        if eigen_square_sum > 1e-12
        else 1.0
    )
    effective_limit = float(len(symbols))
    risk_enb = float(np.clip(risk_enb, 1.0, effective_limit))
    correlation_enb = float(np.clip(correlation_enb, 1.0, effective_limit))
    diversification = DiversificationSummary(
        effective_bets_risk=round(risk_enb, 4),
        effective_bets_correlation=round(correlation_enb, 4),
        interpretation=(
            f"{len(symbols)} holdings behave like approximately {risk_enb:.1f} independent "
            "risk bets under the trailing covariance estimate."
        ),
    )
    return RiskCalculation(
        performance=performance,
        holdings=holdings,
        concentration=concentration,
        diversification=diversification,
        returns=returns,
        covariance_daily=covariance_daily,
    )


def _adjacency(edges: list[MstEdgeData]) -> dict[str, list[tuple[str, MstEdgeData]]]:
    adjacency: dict[str, list[tuple[str, MstEdgeData]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.symbol_a, []).append((edge.symbol_b, edge))
        adjacency.setdefault(edge.symbol_b, []).append((edge.symbol_a, edge))
    for neighbours in adjacency.values():
        neighbours.sort(key=lambda item: item[0])
    return adjacency


def _unique_tree_path(
    adjacency: dict[str, list[tuple[str, MstEdgeData]]],
    start: str,
    end: str,
) -> tuple[list[str], list[MstEdgeData]]:
    queue: deque[str] = deque([start])
    previous: dict[str, tuple[str, MstEdgeData] | None] = {start: None}
    while queue:
        current = queue.popleft()
        if current == end:
            break
        for neighbour, edge in adjacency.get(current, []):
            if neighbour not in previous:
                previous[neighbour] = (current, edge)
                queue.append(neighbour)
    if end not in previous:
        raise ValueError(f"No MST path connects {start} and {end}")
    nodes = [end]
    path_edges: list[MstEdgeData] = []
    current = end
    while True:
        link = previous[current]
        if link is None:
            break
        parent, edge = link
        path_edges.append(edge)
        nodes.append(parent)
        current = parent
    nodes.reverse()
    path_edges.reverse()
    return nodes, path_edges


def _mst_clusters(
    all_symbols: set[str],
    edges: list[MstEdgeData],
    holdings: dict[str, float],
) -> tuple[list[MstClusterSummary], float]:
    retained = [edge for edge in edges if edge.correlation >= MST_CLUSTER_CORRELATION_FLOOR]
    adjacency = _adjacency(retained)
    component_by_symbol: dict[str, str] = {}
    component_members: dict[str, list[str]] = {}
    for symbol in sorted(all_symbols):
        if symbol in component_by_symbol:
            continue
        queue: deque[str] = deque([symbol])
        members: list[str] = []
        component_by_symbol[symbol] = symbol
        while queue:
            current = queue.popleft()
            members.append(current)
            for neighbour, _edge in adjacency.get(current, []):
                if neighbour not in component_by_symbol:
                    component_by_symbol[neighbour] = symbol
                    queue.append(neighbour)
        canonical = min(members)
        for member in members:
            component_by_symbol[member] = canonical
        component_members[canonical] = sorted(members)

    portfolio_components: dict[str, list[str]] = {}
    for symbol in holdings:
        component = component_by_symbol[symbol]
        portfolio_components.setdefault(component, []).append(symbol)
    weighted_components = [
        (
            component,
            sum(holdings[symbol] for symbol in member_symbols),
            sorted(member_symbols),
        )
        for component, member_symbols in portfolio_components.items()
    ]
    weighted_components.sort(key=lambda item: (-item[1], item[0]))
    clusters = [
        MstClusterSummary(
            cluster_id=f"MST cluster {index}",
            weight=round(weight, 8),
            holding_symbols=member_symbols,
            full_node_count=len(component_members[component]),
        )
        for index, (component, weight, member_symbols) in enumerate(weighted_components, start=1)
    ]
    cluster_hhi = sum(cluster.weight * cluster.weight for cluster in clusters)
    return clusters, cluster_hhi


def calculate_mst_diagnostics(
    run_id: str,
    as_of: date,
    all_symbols: set[str],
    edges: list[MstEdgeData],
    holdings: dict[str, float],
    comparison_windows: list[tuple[date, list[MstEdgeData]]] | None = None,
) -> MstPortfolioSummary:
    """Describe direct and indirect relationships between holdings on the full MST."""
    adjacency = _adjacency(edges)
    stability, edge_persistence = calculate_mst_stability(
        [(as_of, edges), *(comparison_windows or [])]
    )
    holding_symbols = sorted(holdings)
    direct_edges = [
        MstEdgeSummary(
            symbol_a=edge.symbol_a,
            symbol_b=edge.symbol_b,
            correlation=round(edge.correlation, 8),
            distance=round(edge.distance, 8),
            persistence=edge_persistence[_edge_key(edge.symbol_a, edge.symbol_b)],
            confidence=_stability_confidence(
                edge_persistence[_edge_key(edge.symbol_a, edge.symbol_b)]
            ),
        )
        for edge in edges
        if edge.symbol_a in holdings and edge.symbol_b in holdings
    ]
    direct_edges.sort(key=lambda edge: (-edge.correlation, edge.symbol_a, edge.symbol_b))

    paths: list[MstPathSummary] = []
    bridge_counts: Counter[str] = Counter()
    subtree_edge_data: dict[tuple[str, str], MstEdgeData] = {}
    for left_index, symbol_a in enumerate(holding_symbols):
        for symbol_b in holding_symbols[left_index + 1 :]:
            nodes, path_edges = _unique_tree_path(adjacency, symbol_a, symbol_b)
            correlations = [edge.correlation for edge in path_edges]
            path_persistence = [
                edge_persistence[_edge_key(edge.symbol_a, edge.symbol_b)] for edge in path_edges
            ]
            minimum_persistence = (
                min(value for value in path_persistence if value is not None)
                if all(value is not None for value in path_persistence)
                else None
            )
            for edge in path_edges:
                key = (
                    min(edge.symbol_a, edge.symbol_b),
                    max(edge.symbol_a, edge.symbol_b),
                )
                subtree_edge_data[key] = edge
            for bridge in nodes[1:-1]:
                bridge_counts[bridge] += 1
            paths.append(
                MstPathSummary(
                    symbol_a=symbol_a,
                    symbol_b=symbol_b,
                    hops=len(path_edges),
                    average_correlation=round(float(np.mean(correlations)), 8),
                    weakest_correlation=round(min(correlations), 8),
                    positive_path_product=round(
                        math.prod(max(correlation, 0.0) for correlation in correlations), 8
                    ),
                    path=nodes,
                    minimum_edge_persistence=minimum_persistence,
                    confidence=_stability_confidence(minimum_persistence),
                )
            )
    paths.sort(
        key=lambda path: (
            path.hops,
            -path.average_correlation,
            path.symbol_a,
            path.symbol_b,
        )
    )
    bridges = [
        MstBridgeSummary(
            symbol=symbol,
            path_pair_count=count,
            is_holding=symbol in holdings,
        )
        for symbol, count in sorted(bridge_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    subtree_edges = [
        MstEdgeSummary(
            symbol_a=edge.symbol_a,
            symbol_b=edge.symbol_b,
            correlation=round(edge.correlation, 8),
            distance=round(edge.distance, 8),
            persistence=edge_persistence[_edge_key(edge.symbol_a, edge.symbol_b)],
            confidence=_stability_confidence(
                edge_persistence[_edge_key(edge.symbol_a, edge.symbol_b)]
            ),
        )
        for _key, edge in sorted(subtree_edge_data.items())
    ]
    clusters, cluster_hhi = _mst_clusters(all_symbols, edges, holdings)
    return MstPortfolioSummary(
        run_id=run_id,
        as_of=as_of,
        cluster_correlation_floor=MST_CLUSTER_CORRELATION_FLOOR,
        direct_edges=direct_edges,
        subtree_edges=subtree_edges,
        holding_paths=paths,
        bridge_stocks=bridges,
        clusters=clusters,
        cluster_hhi=round(cluster_hhi, 8),
        effective_clusters=round(1.0 / cluster_hhi, 4),
        stability=stability,
    )


def calculate_stress(
    scenario: StressScenarioInput | None,
    returns: pd.DataFrame,
    holdings: dict[str, float],
    industries: dict[str, str],
) -> StressScenarioResult | None:
    """Calculate transparent stock-beta or parallel-industry stress estimates."""
    if scenario is None:
        return None
    target = scenario.target.upper() if scenario.kind == "stock" else scenario.target
    if scenario.kind == "stock" and target not in holdings:
        raise ValueError(f"Stress stock must be a portfolio holding: {target}")
    portfolio_industries = set(industries.values())
    if scenario.kind == "industry" and target not in portfolio_industries:
        raise ValueError(f"Stress industry is not represented in the portfolio: {target}")

    shock_decimal = scenario.shock_percent / 100.0
    sensitivities: dict[str, float] = {}
    if scenario.kind == "stock":
        target_returns = returns[target].to_numpy(dtype=np.float64)
        target_variance = float(np.var(target_returns, ddof=1))
        for symbol in holdings:
            if symbol == target:
                sensitivities[symbol] = 1.0
            elif target_variance > 1e-12:
                covariance = float(
                    np.cov(returns[symbol].to_numpy(dtype=np.float64), target_returns, ddof=1)[0, 1]
                )
                sensitivities[symbol] = covariance / target_variance
            else:
                sensitivities[symbol] = 0.0
        method = "Trailing sample regression beta to the selected holding"
        assumptions = [
            "Historical linear sensitivities remain unchanged during the hypothetical shock.",
            "The selected holding receives the exact shock; other holdings move by estimated beta.",
            "Liquidity, feedback effects, execution costs and independent simultaneous "
            "shocks are excluded.",
        ]
    else:
        sensitivities = {
            symbol: 1.0 if industries[symbol] == target else 0.0 for symbol in holdings
        }
        method = "Parallel shock to portfolio holdings in the selected industry"
        assumptions = [
            "Every represented holding in the selected industry receives the same "
            "percentage shock.",
            "Holdings outside the selected industry are unchanged.",
            "Liquidity, feedback effects and cross-industry propagation are excluded.",
        ]

    results: list[StressHoldingResult] = []
    portfolio_impact = 0.0
    for symbol, weight in holdings.items():
        estimated_return = sensitivities[symbol] * shock_decimal
        contribution = weight * estimated_return
        portfolio_impact += contribution
        results.append(
            StressHoldingResult(
                symbol=symbol,
                sensitivity=round(sensitivities[symbol], 6),
                estimated_return_percent=round(estimated_return * 100.0, 6),
                portfolio_contribution_percent=round(contribution * 100.0, 6),
            )
        )
    results.sort(key=lambda result: (-abs(result.portfolio_contribution_percent), result.symbol))
    return StressScenarioResult(
        kind=scenario.kind,
        target=target,
        shock_percent=scenario.shock_percent,
        method=method,
        portfolio_impact_percent=round(portfolio_impact * 100.0, 6),
        results=results,
        assumptions=assumptions,
        disclaimer="Scenario estimate, not a prediction or investment recommendation.",
    )
