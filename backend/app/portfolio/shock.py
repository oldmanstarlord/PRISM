"""Portfolio shock simulator engine (SRS FR-I2, OQ-6).

Simulates propagation of a hypothetical asset shock through:
1. Pairwise regression beta (primary default per user confirmation):
    beta_{j,s} = Cov(r_j, r_s) / Var(r_s)
    impact_j = beta_{j,s} * shock_pct (with impact_s = shock_pct)
2. Optional MST-path decay mode (for comparison):
    Decay along unique MST tree path: product of max(0, rho_{uv}) along edges.

Always includes:
- Banner text: "Scenario estimate, not a prediction"
- Explicit modeling assumptions and limitations
- Portfolio-level impact and asset contributions
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.model_config import ShockSimulatorConfig, load_model_config
from backend.app.db.models import (
    MstEdge,
    Portfolio,
    PortfolioHolding,
    SecurityAlias,
    ShockResult,
    ShockScenario,
)
from backend.app.mst_diagnostics.service import get_latest_mst_run_for_variant
from backend.app.portfolio.covariance import get_adjusted_returns_panel


def calculate_regression_betas(
    returns_df: pd.DataFrame,
    shocked_col: Any,
) -> dict[Any, float]:
    """Compute pairwise regression beta of each column on the shocked column.

    Formula:
        beta_{j,s} = Cov(r_j, r_s) / Var(r_s)
    """
    if returns_df.empty or shocked_col not in returns_df.columns:
        return {}

    r_s = returns_df[shocked_col].values
    var_s = float(np.var(r_s, ddof=1))
    if var_s <= 1e-12:
        return {col: 1.0 if col == shocked_col else 0.0 for col in returns_df.columns}

    betas: dict[Any, float] = {}
    for col in returns_df.columns:
        if col == shocked_col:
            betas[col] = 1.0
            continue
        r_j = returns_df[col].values
        cov_js = float(np.cov(r_j, r_s, ddof=1)[0, 1])
        betas[col] = float(cov_js / var_s)

    return betas


def calculate_mst_path_decay(
    edges: list[tuple[str, str, float]],
    shocked_symbol: str,
    target_symbols: list[str],
) -> dict[str, float]:
    """Calculate shock decay along the unique path in the Minimum Spanning Tree.

    Decay factor D_{s, j} = prod_{(u, v) in path} max(0.0, rho_{u, v}).
    For shocked symbol, D_{s, s} = 1.0.
    """
    adj: dict[str, list[tuple[str, float]]] = {}
    for u, v, corr in edges:
        adj.setdefault(u, []).append((v, corr))
        adj.setdefault(v, []).append((u, corr))

    decay_factors: dict[str, float] = {s: 0.0 for s in target_symbols}
    decay_factors[shocked_symbol] = 1.0

    # BFS to find paths from shocked_symbol in the tree
    queue: deque[tuple[str, float]] = deque([(shocked_symbol, 1.0)])
    visited: set[str] = {shocked_symbol}

    while queue:
        curr, curr_factor = queue.popleft()
        if curr in decay_factors:
            decay_factors[curr] = curr_factor

        for nbr, corr in adj.get(curr, []):
            if nbr not in visited:
                visited.add(nbr)
                # Propagation attenuation using non-negative correlation
                edge_attenuation = max(0.0, corr)
                queue.append((nbr, curr_factor * edge_attenuation))

    return decay_factors


def simulate_portfolio_shock(
    session: Session,
    portfolio_id: UUID,
    shocked_symbol: str,
    shock_pct: float,
    method: str = "regression_beta",
    config: ShockSimulatorConfig | None = None,
) -> tuple[ShockScenario, list[ShockResult], dict[str, Any]]:
    """Simulate shock propagation across portfolio holdings.

    Args:
        session: DB session.
        portfolio_id: UUID of target portfolio.
        shocked_symbol: Symbol of the asset experiencing the exogenous shock.
        shock_pct: Percentage shock (e.g. -10.0 for -10%).
        method: "regression_beta" or "mst_path_decay".
        config: Optional configuration override.

    Returns:
        (scenario, results, envelope_dict)
    """
    if config is None:
        try:
            cfg_envelope = load_model_config(session, "shock_simulator", approved_only=True)
            config = ShockSimulatorConfig(**cfg_envelope.configuration)
        except Exception:
            config = ShockSimulatorConfig()

    # Validate shock range
    if not (config.min_shock_pct <= shock_pct <= config.max_shock_pct):
        raise ValueError(
            f"Shock percentage {shock_pct}% is outside the permitted range "
            f"[{config.min_shock_pct}%, {config.max_shock_pct}%]."
        )

    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise ValueError(f"Portfolio {portfolio_id} not found.")

    # Fetch holdings
    holdings_stmt = select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id)
    holdings = session.scalars(holdings_stmt).all()
    if not holdings:
        raise ValueError(f"Portfolio {portfolio_id} has no holdings.")

    as_of = max(h.as_of for h in holdings)

    # Resolve shocked security
    alias_stmt = select(SecurityAlias.security_id).where(
        func.upper(SecurityAlias.symbol) == shocked_symbol.upper()
    )
    shocked_sec_id = session.scalars(alias_stmt).first()

    # Collect all security IDs needed (portfolio risky assets + shocked security)
    risky_holdings = [h for h in holdings if h.symbol.upper() not in ("CASH", "INR")]
    needed_sec_ids: set[UUID] = {h.security_id for h in risky_holdings if h.security_id is not None}
    if shocked_sec_id is not None:
        needed_sec_ids.add(shocked_sec_id)

    # Fetch returns panel
    returns_df, _ = get_adjusted_returns_panel(
        session=session,
        security_ids=list(needed_sec_ids),
        as_of=as_of,
        window_size=config.window_size,
    )

    method_version = config.method_version if method == "regression_beta" else "shock_mst_decay_v1"

    # Compute impacts
    impacts: dict[str, float] = {}
    betas: dict[str, float] = {}

    # Map security ID back to symbol
    sec_id_to_sym: dict[UUID, str] = {
        h.security_id: h.symbol for h in risky_holdings if h.security_id is not None
    }
    if shocked_sec_id:
        sec_id_to_sym[shocked_sec_id] = shocked_symbol.upper()

    if method == "regression_beta" and not returns_df.empty:
        # Shocked column
        shocked_col = (
            shocked_sec_id if shocked_sec_id in returns_df.columns else shocked_symbol.upper()
        )
        col_betas = calculate_regression_betas(returns_df, shocked_col)
        for col, b in col_betas.items():
            sym = sec_id_to_sym.get(col, str(col))
            betas[sym] = b
            impacts[sym] = b * shock_pct

    elif method == "mst_path_decay":
        # Fetch latest MST edges
        latest_mst = get_latest_mst_run_for_variant(session, variant="raw")
        edges: list[tuple[str, str, float]] = []
        if latest_mst:
            mst_stmt = select(MstEdge.symbol_a, MstEdge.symbol_b, MstEdge.correlation).where(
                MstEdge.mst_run_id == latest_mst.id
            )
            edge_rows = session.execute(mst_stmt).all()
            edges = [
                (
                    r.symbol_a or "",
                    r.symbol_b or "",
                    float(r.correlation) if r.correlation is not None else 0.0,
                )
                for r in edge_rows
            ]
        target_syms = [h.symbol.upper() for h in risky_holdings]

        decay_map = calculate_mst_path_decay(
            edges=edges,
            shocked_symbol=shocked_symbol.upper(),
            target_symbols=target_syms,
        )
        for sym, decay in decay_map.items():
            impacts[sym] = decay * shock_pct
            betas[sym] = decay

    # Always enforce: shocked asset experiences its exact shock
    impacts[shocked_symbol.upper()] = float(shock_pct)
    betas[shocked_symbol.upper()] = 1.0

    # CASH / INR has zero beta and zero impact
    impacts["CASH"] = 0.0
    impacts["INR"] = 0.0
    betas["CASH"] = 0.0
    betas["INR"] = 0.0

    # Build DB Scenario
    scenario = ShockScenario(
        id=uuid4(),
        portfolio_id=portfolio_id,
        shocked_security_id=shocked_sec_id,
        shock_pct=round(shock_pct, 4),
        method_version=method_version,
        created_at=datetime.now(UTC),
    )
    session.add(scenario)

    results: list[ShockResult] = []
    portfolio_impact = 0.0

    for h in holdings:
        sym = h.symbol.upper()
        w = float(h.weight)
        est_impact = impacts.get(sym, 0.0)
        contrib = w * est_impact
        portfolio_impact += contrib

        detail = {
            "symbol": sym,
            "sensitivity": round(betas.get(sym, 0.0), 4),
            "sensitivity_type": "beta" if method == "regression_beta" else "path_decay",
        }

        res = ShockResult(
            id=uuid4(),
            scenario_id=scenario.id,
            security_id=h.security_id,
            weight=round(w, 8),
            estimated_impact_pct=round(est_impact, 6),
            contribution_pct=round(contrib, 6),
            method_detail=detail,
        )
        session.add(res)
        results.append(res)

    session.commit()
    session.refresh(scenario)

    # Sort results by absolute contribution descending
    results.sort(key=lambda r: abs(float(r.contribution_pct)), reverse=True)

    assumptions = [
        (
            f"Linear co-movement: asset sensitivity to {shocked_symbol.upper()} estimated "
            f"over trailing {config.window_size} trading days is assumed constant."
        ),
        (
            "No liquidity feedback or execution slippage: prices are assumed to adjust "
            "without order-book market impact or liquidation cascades."
        ),
        (
            "Covariance stability: historical dependence structure is assumed to hold "
            "during the hypothetical stress scenario."
        ),
        (
            f"Isolated shock: the scenario models an isolated shock to {shocked_symbol.upper()} "
            "without contemporaneous independent shocks to other portfolio assets."
        ),
    ]

    envelope = {
        "banner": config.disclaimer_banner,
        "portfolio_id": str(portfolio_id),
        "shocked_symbol": shocked_symbol.upper(),
        "shock_pct": shock_pct,
        "method": method,
        "method_version": method_version,
        "window_size": config.window_size,
        "portfolio_impact_pct": round(portfolio_impact, 4),
        "assumptions": assumptions,
        "computed_at": datetime.now(UTC).isoformat(),
    }

    return scenario, results, envelope
