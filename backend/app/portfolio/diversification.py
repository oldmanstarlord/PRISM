"""Portfolio diversification analysis engine (SRS FR-I1, OQ-5).

Computes Effective Number of Bets (ENB):
- Risk-contribution entropy ENB (primary default per user confirmation):
    ENB_entropy = exp(- sum p_i ln p_i) where p_i = PRC_i (clamped for p_i > 0)
- Eigenvalue ENB (secondary):
    ENB_eigen = (sum lambda_i)^2 / sum lambda_i^2 where lambda_i are
    eigenvalues of the shrunk correlation matrix.

Also produces:
- Cluster concentration analysis based on latest Layer 2 MST clusters
- Candidate suggestions with low average correlation to reduce concentration
  (worded "would reduce concentration", never "buy").
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.model_config import (
    PortfolioDiversificationConfig,
    canonical_json_hash,
    load_model_config,
)
from backend.app.db.models import (
    DiversificationRun,
    MstCluster,
    PortfolioHolding,
    PortfolioRiskContribution,
    PortfolioRiskRun,
    Security,
    SecurityAlias,
    SecurityMarketStat,
    StockRiskResult,
)
from backend.app.mst_diagnostics.service import get_latest_mst_run_for_variant
from backend.app.portfolio.covariance import compute_covariance, get_adjusted_returns_panel

logger = logging.getLogger(__name__)


def calculate_eigenvalue_enb(corr_matrix: np.ndarray) -> float:
    """Compute Effective Number of Bets from eigenvalue decomposition of correlation matrix.

    Formula:
        ENB_eigen = (sum lambda_i)^2 / sum lambda_i^2

    Invariants:
        - For an identity correlation matrix (uncorrelated assets), ENB == N.
        - For a matrix of ones (perfectly correlated assets), ENB == 1.
    """
    n = corr_matrix.shape[0]
    if n <= 1:
        return 1.0

    # Ensure symmetric
    corr_sym = (corr_matrix + corr_matrix.T) / 2.0
    eigenvals = np.linalg.eigvalsh(corr_sym)

    # Eigenvalues of valid correlation matrix are >= 0; clip numeric noise
    eigenvals = np.maximum(eigenvals, 0.0)

    sum_eigen = float(np.sum(eigenvals))
    sum_sq_eigen = float(np.sum(eigenvals**2))

    if sum_sq_eigen <= 1e-12:
        return 1.0

    enb = (sum_eigen**2) / sum_sq_eigen
    # Bound between 1.0 and N
    return float(np.clip(enb, 1.0, float(n)))


def calculate_entropy_enb(risk_contributions: list[float] | np.ndarray) -> float:
    """Compute Effective Number of Bets from risk contribution entropy.

    Formula:
        ENB_entropy = exp(- sum p_i ln p_i) where p_i = PRC_i (clamped for p_i > 0)

    Invariants:
        - Equal risk contribution across N assets (p_i = 1/N) => ENB == N.
        - Single asset carries 100% of risk (p_1 = 1, p_{i>1} = 0) => ENB == 1.
    """
    p = np.asarray(risk_contributions, dtype=np.float64)
    if len(p) <= 1:
        return 1.0

    # Clamp negative contributions (e.g. hedging assets) to 0 for entropy computation
    p_pos = np.maximum(p, 0.0)
    total_p = float(np.sum(p_pos))

    if total_p <= 1e-12:
        return 1.0

    p_norm = p_pos / total_p
    # Entropy: - sum p_i ln(p_i)
    mask = p_norm > 1e-12
    entropy = -float(np.sum(p_norm[mask] * np.log(p_norm[mask])))
    enb = float(np.exp(entropy))

    # Bound between 1.0 and N
    return float(np.clip(enb, 1.0, float(len(p))))


def analyze_cluster_concentration(
    holdings: list[dict[str, Any]],
    symbol_to_cluster: dict[str, str],
    high_concentration_threshold: float = 0.40,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compute cluster weights and generate plain-language findings.

    Args:
        holdings: list of dicts with 'symbol' and 'weight'.
        symbol_to_cluster: mapping from symbol to cluster_id.
        high_concentration_threshold: fraction (e.g. 0.40) above which a single cluster is flagged.

    Returns:
        (cluster_weights_dict, findings_list)
    """
    cluster_weights: dict[str, float] = {}
    cluster_members: dict[str, list[str]] = {}

    for h in holdings:
        sym = h["symbol"]
        weight = float(h["weight"])
        cid = symbol_to_cluster.get(sym, "UNCLUSTERED")
        cluster_weights[cid] = cluster_weights.get(cid, 0.0) + weight
        cluster_members.setdefault(cid, []).append(sym)

    # Sort clusters by weight descending
    sorted_clusters = sorted(cluster_weights.items(), key=lambda kv: kv[1], reverse=True)
    findings: list[dict[str, Any]] = []

    total_holdings = len(holdings)
    for cid, w in sorted_clusters:
        members = cluster_members[cid]
        if w >= high_concentration_threshold and cid != "UNCLUSTERED":
            findings.append(
                {
                    "severity": "high",
                    "cluster_id": cid,
                    "weight": round(w, 4),
                    "holding_count": len(members),
                    "total_holdings": total_holdings,
                    "message": (
                        f"Cluster concentration: {len(members)} of {total_holdings} holdings "
                        f"sit in MST cluster '{cid}', representing "
                        f"{w * 100:.1f}% of total portfolio weight."
                    ),
                    "members": members,
                }
            )

    if not findings:
        top_cid, top_w = sorted_clusters[0] if sorted_clusters else ("NONE", 0.0)
        findings.append(
            {
                "severity": "info",
                "cluster_id": top_cid,
                "weight": round(top_w, 4),
                "holding_count": len(cluster_members.get(top_cid, [])),
                "total_holdings": total_holdings,
                "message": (
                    f"Portfolio holdings are distributed across {len(cluster_weights)} "
                    f"MST clusters, with the largest cluster ({top_cid}) "
                    f"representing {top_w * 100:.1f}% of portfolio weight."
                ),
                "members": cluster_members.get(top_cid, []),
            }
        )

    cluster_weights_payload = {cid: round(w, 6) for cid, w in sorted_clusters}
    return cluster_weights_payload, findings


def generate_candidate_suggestions(
    session: Session,
    current_symbols: list[str],
    as_of: datetime | Any,
    holdings_returns_df: pd.DataFrame,
    holdings_weights: dict[str, float],
    min_confidence: float = 60.0,
    min_adv_20: float = 10000000.0,
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    """Scan universe securities with low average correlation to portfolio to reduce concentration.

    Wording strictly uses 'would reduce concentration', never 'buy'.
    """
    if holdings_returns_df.empty:
        return []

    as_of_date = as_of if hasattr(as_of, "year") else datetime.now(UTC).date()
    if isinstance(as_of, datetime):
        as_of_date = as_of.date()

    # Query active securities not in current holdings
    sec_stmt = (
        select(Security.id, SecurityAlias.symbol, Security.company_name, Security.industry)
        .join(SecurityAlias, Security.id == SecurityAlias.security_id)
        .where(
            Security.is_active.is_(True),
            ~SecurityAlias.symbol.in_(current_symbols),
        )
        .limit(100)
    )
    candidate_secs = session.execute(sec_stmt).all()
    if not candidate_secs:
        return []

    cand_sec_map = {row.id: row for row in candidate_secs}

    cand_ids = list(cand_sec_map.keys())

    # Filter for liquidity
    stat_stmt = (
        select(SecurityMarketStat.security_id, SecurityMarketStat.adv_20)
        .where(
            SecurityMarketStat.security_id.in_(cand_ids),
            SecurityMarketStat.trade_date <= as_of_date,
            SecurityMarketStat.adv_20 >= min_adv_20,
        )
        .order_by(SecurityMarketStat.trade_date.desc())
    )
    stat_rows = session.execute(stat_stmt).all()
    liquid_sec_ids: set[UUID] = {row.security_id for row in stat_rows}
    adv_map = {row.security_id: float(row.adv_20) for row in stat_rows if row.adv_20 is not None}

    # If stock risk results exist, filter by confidence
    score_stmt = (
        select(StockRiskResult.security_id, StockRiskResult.confidence)
        .where(
            StockRiskResult.security_id.in_(cand_ids),
            StockRiskResult.confidence >= min_confidence,
        )
        .order_by(StockRiskResult.computed_at.desc())
    )
    score_rows = session.execute(score_stmt).all()
    conf_map = {row.security_id: float(row.confidence) for row in score_rows}

    # Eligible candidates (prioritize those passing filters,
    # fallback gracefully if DB has no market stats loaded yet)
    eligible_ids = [
        sid
        for sid in cand_ids
        if (sid in liquid_sec_ids or not liquid_sec_ids) and (sid in conf_map or not conf_map)
    ][:30]

    if not eligible_ids:
        eligible_ids = cand_ids[:20]

    # Fetch returns for eligible candidates
    cand_returns_df, _ = get_adjusted_returns_panel(
        session=session,
        security_ids=eligible_ids,
        as_of=as_of_date,
        window_size=len(holdings_returns_df),
    )

    if cand_returns_df.empty:
        return []

    # Map candidate DataFrame columns to Security objects
    suggestions: list[dict[str, Any]] = []
    # Align dates between portfolio and candidates
    common_dates = holdings_returns_df.index.intersection(cand_returns_df.index)
    if len(common_dates) < 20:
        return []

    p_returns = holdings_returns_df.loc[common_dates]
    c_returns = cand_returns_df.loc[common_dates]

    # Compute correlation of each candidate with portfolio holdings
    # Portfolio weighted return
    holding_cols = [c for c in p_returns.columns if c in holdings_weights]
    if not holding_cols:
        return []

    weights_vec = np.array([holdings_weights[c] for c in holding_cols], dtype=np.float64)
    total_w = np.sum(weights_vec)
    if total_w > 0:
        weights_vec = weights_vec / total_w

    portfolio_daily_ret = p_returns[holding_cols].values @ weights_vec

    for col in c_returns.columns:
        cand_series = c_returns[col].values
        # std check
        if np.std(cand_series) < 1e-9 or np.std(portfolio_daily_ret) < 1e-9:
            continue
        corr = float(np.corrcoef(cand_series, portfolio_daily_ret)[0, 1])
        if np.isnan(corr):
            continue

        sec_row = cand_sec_map.get(col)
        if not sec_row:
            continue

        sym = sec_row.symbol
        ind = sec_row.industry or "General"
        suggestions.append(
            {
                "security_id": str(sec_row.id),
                "symbol": sym,
                "name": sec_row.company_name,
                "industry": ind,
                "average_correlation": round(corr, 4),
                "adv_20": adv_map.get(sec_row.id),
                "confidence": conf_map.get(sec_row.id),
                "rationale": (
                    f"Adding {sym} ({ind}) would reduce concentration "
                    f"(correlation {corr:.2f} with portfolio holdings)."
                ),
            }
        )

    # Sort by lowest correlation
    suggestions.sort(key=lambda s: s["average_correlation"])
    return suggestions[:max_candidates]


def run_portfolio_diversification(
    session: Session,
    portfolio_risk_run_id: UUID,
    config: PortfolioDiversificationConfig | None = None,
) -> DiversificationRun:
    """Execute or retrieve idempotent diversification analysis for a portfolio risk run.

    D6 Idempotent: If a run with the same config fingerprint exists, returns it immediately.
    """
    # Load portfolio risk run
    risk_run = session.get(PortfolioRiskRun, portfolio_risk_run_id)
    if not risk_run:
        raise ValueError(f"PortfolioRiskRun {portfolio_risk_run_id} not found.")

    if config is None:
        try:
            cfg_envelope = load_model_config(
                session, "portfolio_diversification", approved_only=True
            )
            config = PortfolioDiversificationConfig(**cfg_envelope.configuration)
        except Exception:
            config = PortfolioDiversificationConfig()

    cfg_dict = config.model_dump()
    cfg_fingerprint = canonical_json_hash(cfg_dict)

    # Check for existing run
    existing = session.scalars(
        select(DiversificationRun).where(
            DiversificationRun.portfolio_risk_run_id == portfolio_risk_run_id,
            DiversificationRun.config_fingerprint == cfg_fingerprint,
        )
    ).first()
    if existing:
        return existing

    # Fetch risk contributions
    contrib_stmt = select(PortfolioRiskContribution).where(
        PortfolioRiskContribution.run_id == portfolio_risk_run_id
    )
    contrib_rows = session.scalars(contrib_stmt).all()
    if not contrib_rows:
        raise ValueError(
            f"No risk contributions found for PortfolioRiskRun {portfolio_risk_run_id}."
        )

    # 1. ENB from risk contribution entropy
    prc_values = [float(r.percent_contribution) for r in contrib_rows]
    enb_entropy = calculate_entropy_enb(prc_values)

    # 2. ENB from eigenvalue decomposition of correlation matrix
    # Fetch holdings
    holdings_stmt = select(PortfolioHolding).where(
        PortfolioHolding.portfolio_id == risk_run.portfolio_id,
        PortfolioHolding.as_of == risk_run.as_of,
    )
    holdings = session.scalars(holdings_stmt).all()
    # Filter risky holdings (exclude CASH)
    risky_holdings = [h for h in holdings if h.symbol.upper() not in ("CASH", "INR")]
    risky_sec_ids = [h.security_id for h in risky_holdings if h.security_id is not None]

    if len(risky_sec_ids) >= 2:
        returns_df, _ = get_adjusted_returns_panel(
            session=session,
            security_ids=risky_sec_ids,
            as_of=risk_run.as_of,
            window_size=risk_run.window_size,
        )
        cov_matrix, _ = compute_covariance(
            returns_df,
            annualise=False,
        )
        # Derive correlation matrix
        vols = np.sqrt(np.diag(cov_matrix))
        outer_vols = np.outer(vols, vols)
        with np.errstate(divide="ignore", invalid="ignore"):
            corr_matrix = np.where(outer_vols > 1e-12, cov_matrix / outer_vols, 0.0)
        np.fill_diagonal(corr_matrix, 1.0)
        enb_eigen = calculate_eigenvalue_enb(corr_matrix)
    else:
        enb_eigen = 1.0
        returns_df = pd.DataFrame()

    # 3. Cluster concentration findings
    # Fetch latest MST clusters
    latest_mst = get_latest_mst_run_for_variant(session, variant="raw")
    if latest_mst:
        mst_stmt = select(MstCluster.symbol, MstCluster.cluster_id).where(
            MstCluster.run_id == latest_mst.id
        )
        cluster_rows = session.execute(mst_stmt).all()
        symbol_to_cluster = {row.symbol: row.cluster_id for row in cluster_rows}
    else:
        symbol_to_cluster = {}

    holdings_dict = [{"symbol": h.symbol, "weight": float(h.weight)} for h in holdings]
    cluster_weights, findings = analyze_cluster_concentration(
        holdings=holdings_dict,
        symbol_to_cluster=symbol_to_cluster,
        high_concentration_threshold=(
            config.cluster_concentration_rules.high_concentration_threshold
        ),
    )

    # 4. Candidate suggestions
    holdings_weights = {h.symbol: float(h.weight) for h in holdings}
    current_symbols = [h.symbol for h in holdings]
    suggestions = generate_candidate_suggestions(
        session=session,
        current_symbols=current_symbols,
        as_of=risk_run.as_of,
        holdings_returns_df=returns_df,
        holdings_weights=holdings_weights,
        min_confidence=config.candidate_suggestion_rules.min_confidence,
        min_adv_20=config.candidate_suggestion_rules.min_adv_20,
        max_candidates=config.candidate_suggestion_rules.max_candidates,
    )

    # Package findings with candidate suggestions
    findings_payload = {
        "concentration_findings": findings,
        "candidate_suggestions": suggestions,
    }

    div_run = DiversificationRun(
        id=uuid4(),
        portfolio_risk_run_id=portfolio_risk_run_id,
        enb_eigen=round(enb_eigen, 6),
        enb_risk_entropy=round(enb_entropy, 6),
        cluster_weights=cluster_weights,
        findings=findings_payload,
        config_fingerprint=cfg_fingerprint,
        computed_at=datetime.now(UTC),
    )

    session.add(div_run)
    session.commit()
    session.refresh(div_run)
    return div_run
