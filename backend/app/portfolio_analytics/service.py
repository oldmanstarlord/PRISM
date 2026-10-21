"""Read-only orchestration for session-only portfolio analytics."""

from datetime import timedelta
from uuid import UUID

import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.correlation_mst.service import latest_completed_mst_query
from backend.app.db.models import (
    MstEdge,
    MstNode,
    MstRun,
    SectorDivergenceScore,
)
from backend.app.portfolio_analytics.calculator import (
    MstEdgeData,
    calculate_mst_diagnostics,
    calculate_risk,
    calculate_stress,
)
from backend.app.portfolio_analytics.schemas import (
    AnalysisEnvelope,
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
)
from backend.app.sector_divergence.inputs import load_latest_adjusted_closes
from backend.app.sector_divergence.service import latest_completed_run_query

IMPLEMENTATION_VERSION = "portfolio-analytics-v1"
MINIMUM_RETURN_OBSERVATIONS = 60
MST_STABILITY_PRIOR_RUN_COUNT = 4


def _mst_edges_for_run(session: Session, run_id: UUID) -> list[MstEdgeData]:
    stored_edges = session.scalars(
        select(MstEdge).where(MstEdge.mst_run_id == run_id).order_by(MstEdge.edge_rank)
    ).all()
    edges: list[MstEdgeData] = []
    for edge in stored_edges:
        if edge.symbol_a is None or edge.symbol_b is None or edge.correlation is None:
            raise ValueError("A Layer 2 MST comparison run contains an incomplete stored edge")
        edges.append(
            MstEdgeData(
                symbol_a=edge.symbol_a,
                symbol_b=edge.symbol_b,
                correlation=float(edge.correlation),
                distance=float(edge.distance),
            )
        )
    return edges


def _normalized_holdings(payload: PortfolioAnalysisRequest) -> dict[str, float]:
    holdings: dict[str, float] = {}
    for holding in payload.holdings:
        holdings[holding.symbol] = holdings.get(holding.symbol, 0.0) + holding.weight
    total = sum(holdings.values())
    if abs(total - 1.0) > 0.0001:
        raise ValueError(f"Portfolio weights must total 1.0; received {total:.6f}")
    return dict(sorted(holdings.items()))


def analyze_portfolio(
    session: Session,
    payload: PortfolioAnalysisRequest,
) -> PortfolioAnalysisResponse:
    """Calculate a portfolio response without writing holdings or results to the database."""
    holdings = _normalized_holdings(payload)
    mst_run = session.scalar(latest_completed_mst_query())
    if mst_run is None:
        raise ValueError("No completed Layer 2 MST run is available")
    if mst_run.data_cutoff is None:
        raise ValueError("Latest Layer 2 MST run has no point-in-time data cutoff")

    all_nodes = session.scalars(
        select(MstNode).where(MstNode.mst_run_id == mst_run.id).order_by(MstNode.symbol)
    ).all()
    node_by_symbol = {node.symbol: node for node in all_nodes}
    unsupported = sorted(set(holdings) - set(node_by_symbol))
    if unsupported:
        raise ValueError(f"Not in the latest MST universe: {', '.join(unsupported)}")
    industries = {symbol: node_by_symbol[symbol].industry or "Unclassified" for symbol in holdings}

    start_date = mst_run.window_end - timedelta(days=payload.window * 2 + 30)
    observations = load_latest_adjusted_closes(
        session=session,
        security_ids=[node_by_symbol[symbol].security_id for symbol in holdings],
        start_date=start_date,
        end_date=mst_run.window_end,
        data_cutoff=mst_run.data_cutoff,
    )
    symbol_by_security = {node_by_symbol[symbol].security_id: symbol for symbol in holdings}
    dates = sorted({observation.trade_date for observation in observations})
    prices = pd.DataFrame(
        index=pd.Index(dates, name="trade_date"),
        columns=holdings,
        dtype="float64",
    )
    for observation in observations:
        symbol = symbol_by_security.get(observation.security_id)
        if symbol is not None:
            prices.at[observation.trade_date, symbol] = float(observation.adjusted_close)
    common_prices = prices.dropna(axis=0, how="any").tail(payload.window + 1)
    observations_used = len(common_prices) - 1
    if observations_used < MINIMUM_RETURN_OBSERVATIONS:
        raise ValueError(
            "Insufficient common adjusted-price history: "
            f"required {MINIMUM_RETURN_OBSERVATIONS} returns; found {max(observations_used, 0)}"
        )

    divergence_run = session.scalar(latest_completed_run_query())
    divergence: dict[str, tuple[float, str]] = {}
    if divergence_run is not None:
        scores = session.scalars(
            select(SectorDivergenceScore).where(
                SectorDivergenceScore.run_id == divergence_run.id,
                SectorDivergenceScore.horizon == 20,
                SectorDivergenceScore.symbol.in_(holdings),
            )
        ).all()
        divergence = {
            score.symbol: (float(score.divergence_value), score.interpretation) for score in scores
        }

    risk = calculate_risk(common_prices, holdings, industries, divergence)
    edges = _mst_edges_for_run(session, mst_run.id)
    compatible_runs_query = (
        select(MstRun)
        .where(
            MstRun.id != mst_run.id,
            MstRun.status == "completed",
            MstRun.universe_id == mst_run.universe_id,
            MstRun.implementation_version == mst_run.implementation_version,
            MstRun.configuration_hash == mst_run.configuration_hash,
            MstRun.window_end < mst_run.window_end,
        )
        .order_by(desc(MstRun.window_end), desc(MstRun.computed_at))
        .limit(MST_STABILITY_PRIOR_RUN_COUNT)
    )
    compatible_runs = session.scalars(compatible_runs_query).all()
    comparison_windows = [
        (run.window_end, _mst_edges_for_run(session, run.id)) for run in compatible_runs
    ]
    mst = calculate_mst_diagnostics(
        run_id=str(mst_run.id),
        as_of=mst_run.window_end,
        all_symbols=set(node_by_symbol),
        edges=edges,
        holdings=holdings,
        comparison_windows=comparison_windows,
    )
    stress = calculate_stress(payload.stress, risk.returns, holdings, industries)

    findings: list[str] = []
    if observations_used < payload.window:
        findings.append(
            f"Only {observations_used} common returns were available from the requested "
            f"{payload.window}-return window."
        )
    if mst.stability.confidence in {"unavailable", "low"}:
        findings.append(
            "MST-derived paths and clusters have "
            f"{mst.stability.confidence} confidence: {mst.stability.reason}"
        )
    highest_risk = max(risk.holdings, key=lambda holding: holding.risk_contribution)
    findings.append(
        f"{highest_risk.symbol} contributes the largest estimated share of portfolio risk "
        f"at {highest_risk.risk_contribution * 100:.1f}%."
    )
    largest_industry = risk.concentration.industry_weights[0]
    findings.append(
        f"{largest_industry.industry} is the largest industry exposure at "
        f"{largest_industry.weight * 100:.1f}%."
    )
    largest_cluster = mst.clusters[0]
    findings.append(
        f"The largest correlation-defined MST cluster contains "
        f"{', '.join(largest_cluster.holding_symbols)} and "
        f"{largest_cluster.weight * 100:.1f}% of portfolio weight."
    )
    if mst.bridge_stocks:
        bridge = mst.bridge_stocks[0]
        relationship = "holding" if bridge.is_holding else "non-held stock"
        findings.append(
            f"{bridge.symbol} is the most frequent {relationship} bridge across holding-to-holding "
            f"MST paths ({bridge.path_pair_count} paths)."
        )
    unusual = [
        holding.symbol
        for holding in risk.holdings
        if holding.divergence_20d is not None and abs(holding.divergence_20d) >= 2.0
    ]
    if unusual:
        findings.append(f"Strong absolute 20-day divergence is present in {', '.join(unusual)}.")

    envelope = AnalysisEnvelope(
        as_of=mst_run.window_end,
        lookback_start=common_prices.index[0],
        data_cutoff=mst_run.data_cutoff,
        requested_observations=payload.window,
        observations_used=observations_used,
        return_frequency="daily adjusted-close log returns",
        annualisation_factor=252,
        weighting_assumption="constant target weights, rebalanced each trading day",
        missing_data_rule="intersection of complete dates; no forward/backward filling",
        implementation_version=IMPLEMENTATION_VERSION,
    )
    return PortfolioAnalysisResponse(
        envelope=envelope,
        performance=risk.performance,
        holdings=risk.holdings,
        concentration=risk.concentration,
        diversification=risk.diversification,
        mst=mst,
        stress=stress,
        findings=findings,
        limitations=[
            "Historical daily relationships can change and do not predict future returns or risk.",
            "Constant target weights are a simplifying backtest assumption; taxes, costs "
            "and cash flows are excluded.",
            "MST paths are a sparse descriptive summary and are not causal transmission channels.",
            "MST stability compares only compatible stored runs and may be unavailable until a "
            "second distinct market window has been calculated.",
            "Stress estimates exclude liquidity effects, feedback loops and parameter instability.",
            "This analysis is educational and does not provide investment advice.",
        ],
    )
