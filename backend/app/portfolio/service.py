"""Portfolio service orchestration: creation, CSV import, risk runs, and result envelope."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.core.model_config import load_model_config
from backend.app.db.models import (
    AnalyticsArtifact,
    BenchmarkSeries,
    DiversificationRun,
    ModelConfig,
    MstNode,
    MstRun,
    Portfolio,
    PortfolioHolding,
    PortfolioRiskContribution,
    PortfolioRiskRun,
    ScoreRun,
    Security,
    StockRiskResult,
)
from backend.app.portfolio.covariance import (
    compute_covariance,
    get_adjusted_returns_panel,
    persist_covariance_parquet,
)
from backend.app.portfolio.metrics import calculate_portfolio_metrics
from backend.app.portfolio.parser import (
    normalize_portfolio_holdings,
    parse_csv_holdings,
)
from backend.app.portfolio.schemas import (
    DiversificationResponse,
    DrawdownPoint,
    PortfolioCreate,
    PortfolioHoldingOut,
    PortfolioImportResult,
    PortfolioOut,
    PortfolioRiskRunOut,
    PortfolioRiskScoreOut,
    RiskContributionOut,
    RiskRunRequest,
    ShockRequest,
    ShockResultOut,
    ShockScenarioResponse,
)
from backend.app.portfolio.score import HoldingScoreInput, compute_portfolio_score


def _canonical_hash(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_portfolio_input_fingerprint(holdings: list[PortfolioHolding], as_of: date) -> str:
    """Compute deterministic SHA-256 fingerprint from sorted holdings and weights."""
    sorted_items = sorted(
        [
            (
                h.symbol.upper(),
                format(float(h.weight), ".8f"),
                format(float(h.quantity), ".6f") if h.quantity is not None else "none",
            )
            for h in holdings
        ],
        key=lambda x: x[0],
    )
    payload = {
        "as_of": as_of.isoformat(),
        "holdings": sorted_items,
    }
    return _canonical_hash(payload)


def create_portfolio(session: Session, payload: PortfolioCreate) -> PortfolioOut:
    """Create a new portfolio with initial holdings snapshot."""
    as_of = payload.as_of or date.today()

    resolved_holdings, errors, _ = normalize_portfolio_holdings(
        session,
        payload.holdings,
        as_of=as_of,
        source=payload.source,
    )
    if errors:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": [e.model_dump() for e in errors]},
        )

    portfolio = Portfolio(
        name=payload.name,
        description=payload.description,
        owner_ref=payload.owner_ref,
    )
    session.add(portfolio)
    session.flush()

    db_holdings: list[PortfolioHolding] = []
    for rh in resolved_holdings:
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            security_id=rh.security_id,
            symbol=rh.symbol,
            quantity=rh.quantity,
            weight=rh.weight,
            as_of=rh.as_of,
            source=rh.source,
            notes=rh.notes,
        )
        session.add(holding)
        db_holdings.append(holding)

    session.commit()
    session.refresh(portfolio)

    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        description=portfolio.description,
        owner_ref=portfolio.owner_ref,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings=[PortfolioHoldingOut.model_validate(h) for h in db_holdings],
    )


def import_portfolio_csv(
    session: Session,
    name: str,
    csv_content: str,
    as_of: date | None = None,
    description: str | None = None,
    owner_ref: str = "local-user",
) -> PortfolioImportResult:
    """Import portfolio holdings from CSV text with row-level validation."""
    parsed_inputs, parse_errors = parse_csv_holdings(csv_content)
    if parse_errors:
        return PortfolioImportResult(errors=parse_errors)

    eff_as_of = as_of or date.today()
    resolved_holdings, norm_errors, warnings = normalize_portfolio_holdings(
        session,
        parsed_inputs,
        as_of=eff_as_of,
        source="csv_import",
    )
    if norm_errors:
        return PortfolioImportResult(errors=norm_errors, warnings=warnings)

    portfolio = Portfolio(
        name=name,
        description=description,
        owner_ref=owner_ref,
    )
    session.add(portfolio)
    session.flush()

    db_holdings: list[PortfolioHolding] = []
    for rh in resolved_holdings:
        holding = PortfolioHolding(
            portfolio_id=portfolio.id,
            security_id=rh.security_id,
            symbol=rh.symbol,
            quantity=rh.quantity,
            weight=rh.weight,
            as_of=rh.as_of,
            source=rh.source,
            notes=rh.notes,
        )
        session.add(holding)
        db_holdings.append(holding)

    session.commit()
    session.refresh(portfolio)

    port_out = PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        description=portfolio.description,
        owner_ref=portfolio.owner_ref,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings=[PortfolioHoldingOut.model_validate(h) for h in db_holdings],
    )

    return PortfolioImportResult(
        portfolio=port_out,
        warnings=warnings,
    )


def list_portfolios(session: Session, owner_ref: str = "local-user") -> list[PortfolioOut]:
    """List all portfolios owned by owner_ref."""
    stmt = (
        select(Portfolio)
        .where(Portfolio.owner_ref == owner_ref)
        .order_by(Portfolio.created_at.desc())
    )
    portfolios = session.scalars(stmt).all()

    out: list[PortfolioOut] = []
    for p in portfolios:
        holdings = session.scalars(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == p.id)
            .order_by(PortfolioHolding.weight.desc())
        ).all()
        out.append(
            PortfolioOut(
                id=p.id,
                name=p.name,
                description=p.description,
                owner_ref=p.owner_ref,
                created_at=p.created_at,
                updated_at=p.updated_at,
                holdings=[PortfolioHoldingOut.model_validate(h) for h in holdings],
            )
        )
    return out


def get_portfolio(session: Session, portfolio_id: UUID) -> PortfolioOut:
    """Retrieve portfolio details and current holdings."""
    portfolio = session.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found",
        )

    holdings = session.scalars(
        select(PortfolioHolding)
        .where(PortfolioHolding.portfolio_id == portfolio.id)
        .order_by(PortfolioHolding.weight.desc())
    ).all()

    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        description=portfolio.description,
        owner_ref=portfolio.owner_ref,
        created_at=portfolio.created_at,
        updated_at=portfolio.updated_at,
        holdings=[PortfolioHoldingOut.model_validate(h) for h in holdings],
    )


def run_portfolio_risk(
    session: Session,
    portfolio_id: UUID,
    req: RiskRunRequest,
) -> PortfolioRiskRunOut:
    """Execute risk calculations, Ledoit-Wolf shrinkage, and package result envelope."""
    portfolio = session.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found",
        )

    # Determine as_of date: request as_of or latest holding as_of
    if req.as_of is not None:
        eff_as_of = req.as_of
    else:
        latest_date = session.scalar(
            select(func.max(PortfolioHolding.as_of)).where(
                PortfolioHolding.portfolio_id == portfolio_id
            )
        )
        eff_as_of = latest_date or date.today()

    # Query active holdings for eff_as_of (or closest preceding date)
    holdings = session.scalars(
        select(PortfolioHolding)
        .where(
            PortfolioHolding.portfolio_id == portfolio_id,
            PortfolioHolding.as_of <= eff_as_of,
        )
        .order_by(PortfolioHolding.as_of.desc())
    ).all()

    if not holdings:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No holdings found for portfolio {portfolio_id} on or before {eff_as_of}",
        )

    # Deduplicate to latest snapshot date
    snapshot_date = holdings[0].as_of
    active_holdings = [h for h in holdings if h.as_of == snapshot_date]

    # Input fingerprint
    input_fp = compute_portfolio_input_fingerprint(active_holdings, eff_as_of)

    # Config loading
    config_ver = req.config_version or "1.0.0"
    try:
        cfg_envelope = load_model_config(
            session, config_key="portfolio_rules", version=config_ver, approved_only=False
        )
        cfg_fingerprint = cfg_envelope.fingerprint()
        window_size = int(cfg_envelope.configuration.get("default_lookback_days", 250))
        annualisation_factor = float(cfg_envelope.configuration.get("annualisation_factor", 252))
    except Exception:
        # Fallback config
        cfg_fingerprint = hashlib.sha256(
            f"portfolio_rules:{config_ver}:default".encode()
        ).hexdigest()
        window_size = 250
        annualisation_factor = 252.0

    # Idempotency check: reuse completed run if matching input & config fingerprint
    if not req.force_rerun:
        existing_run = session.scalar(
            select(PortfolioRiskRun).where(
                PortfolioRiskRun.portfolio_id == portfolio_id,
                PortfolioRiskRun.input_fingerprint == input_fp,
                PortfolioRiskRun.config_fingerprint == cfg_fingerprint,
                PortfolioRiskRun.as_of == eff_as_of,
                PortfolioRiskRun.status == "completed",
            )
        )
        if existing_run is not None:
            contribs = session.scalars(
                select(PortfolioRiskContribution)
                .where(PortfolioRiskContribution.run_id == existing_run.id)
                .order_by(PortfolioRiskContribution.percent_contribution.desc())
            ).all()
            return PortfolioRiskRunOut(
                id=existing_run.id,
                portfolio_id=existing_run.portfolio_id,
                as_of=existing_run.as_of,
                config_version=existing_run.config_version,
                config_fingerprint=existing_run.config_fingerprint,
                input_fingerprint=existing_run.input_fingerprint,
                window_size=existing_run.window_size,
                annualisation_factor=float(existing_run.annualisation_factor),
                portfolio_volatility=float(existing_run.portfolio_volatility),
                portfolio_variance=float(existing_run.portfolio_variance),
                portfolio_beta=(
                    float(existing_run.portfolio_beta)
                    if existing_run.portfolio_beta is not None
                    else None
                ),
                max_drawdown=float(existing_run.max_drawdown),
                var_historical_95=(
                    float(existing_run.var_historical_95)
                    if existing_run.var_historical_95 is not None
                    else None
                ),
                var_parametric_95=(
                    float(existing_run.var_parametric_95)
                    if existing_run.var_parametric_95 is not None
                    else None
                ),
                es_historical_95=(
                    float(existing_run.es_historical_95)
                    if existing_run.es_historical_95 is not None
                    else None
                ),
                es_parametric_95=(
                    float(existing_run.es_parametric_95)
                    if existing_run.es_parametric_95 is not None
                    else None
                ),
                shrinkage_intensity=float(existing_run.shrinkage_intensity),
                concentration_metrics=dict(existing_run.concentration_metrics or {}),
                drawdown_series=[
                    DrawdownPoint(
                        date=d["date"],
                        drawdown=d["drawdown"],
                        portfolio_return=d["portfolio_return"],
                    )
                    for d in (existing_run.drawdown_series or [])
                    if isinstance(d, dict)
                ],
                contributions=[RiskContributionOut.model_validate(c) for c in contribs],
                status=existing_run.status,
                data_sufficiency=existing_run.data_sufficiency,
                envelope=dict(existing_run.envelope or {}),
                computed_at=existing_run.computed_at,
            )

    # Separate risky holdings
    risky_holdings = [h for h in active_holdings if h.security_id is not None]

    sec_ids = [h.security_id for h in risky_holdings if h.security_id is not None]
    all_symbols = [h.symbol.upper() for h in active_holdings]
    all_weights = [float(h.weight) for h in active_holdings]

    # Query returns panel for risky assets
    returns_df, data_warnings = get_adjusted_returns_panel(
        session, sec_ids, as_of=eff_as_of, window_size=window_size
    )

    # Map column headers to symbols
    sec_to_sym = {h.security_id: h.symbol.upper() for h in risky_holdings}
    returns_df.rename(columns=sec_to_sym, inplace=True)

    # Benchmark series
    bench_stmt = (
        select(BenchmarkSeries.trade_date, BenchmarkSeries.close)
        .where(
            BenchmarkSeries.benchmark_id == "NIFTY_200",
            BenchmarkSeries.trade_date <= eff_as_of,
        )
        .order_by(BenchmarkSeries.trade_date.desc())
        .limit(window_size + 1)
    )
    bench_rows = session.execute(bench_stmt).all()
    bench_returns: pd.Series | None = None
    if len(bench_rows) > 2:
        b_df = pd.DataFrame(bench_rows, columns=["trade_date", "close"]).sort_values("trade_date")
        b_series = b_df.set_index("trade_date")["close"].astype(float)
        bench_returns = np.log(b_series / b_series.shift(1)).dropna()

    # Query industries from Security table
    industries: dict[str, str | None] = {}
    if sec_ids:
        sec_rows = session.execute(
            select(Security.id, Security.industry).where(Security.id.in_(sec_ids))
        ).all()
        id_to_ind = {sid: ind for sid, ind in sec_rows}
        for h in risky_holdings:
            if h.security_id is not None:
                industries[h.symbol.upper()] = id_to_ind.get(h.security_id)

    # Query latest MST clusters if available
    mst_clusters: dict[str, str] = {}
    latest_mst_run_id = session.scalar(
        select(MstRun.id)
        .where(MstRun.window_end <= eff_as_of, MstRun.status == "completed")
        .order_by(MstRun.window_end.desc(), MstRun.computed_at.desc())
        .limit(1)
    )
    if latest_mst_run_id is not None:
        mst_nodes = session.execute(
            select(MstNode.symbol, MstNode.industry).where(MstNode.mst_run_id == latest_mst_run_id)
        ).all()
        # Use MST node industry/cluster label
        for sym, ind in mst_nodes:
            mst_clusters[sym.upper()] = ind

    # Covariance computation
    if not returns_df.empty:
        risky_symbols = [col for col in returns_df.columns]
        cov_risky, shrinkage_intensity = compute_covariance(
            returns_df[risky_symbols],
            shrinkage_override=req.shrinkage_override,
            annualise=True,
            annualisation_factor=annualisation_factor,
        )
    else:
        risky_symbols = []
        cov_risky = np.zeros((0, 0))
        shrinkage_intensity = 0.0

    # Expand covariance matrix to include all assets (risky + cash)
    n_all = len(all_symbols)
    cov_all = np.zeros((n_all, n_all), dtype=np.float64)

    for i, sym_i in enumerate(all_symbols):
        if sym_i in risky_symbols:
            idx_i = risky_symbols.index(sym_i)
            for j, sym_j in enumerate(all_symbols):
                if sym_j in risky_symbols:
                    idx_j = risky_symbols.index(sym_j)
                    cov_all[i, j] = cov_risky[idx_i, idx_j]

    # Calculate metrics
    metrics = calculate_portfolio_metrics(
        symbols=all_symbols,
        weights=all_weights,
        cov_matrix_annual=cov_all,
        returns_df=returns_df,
        benchmark_returns=bench_returns,
        industries=industries,
        mst_clusters=mst_clusters,
        annualisation_factor=annualisation_factor,
    )

    all_warnings = data_warnings + metrics.warnings

    # Result envelope (SRS Section 10 / D3)
    now_utc = datetime.now(UTC)
    run_id = uuid4()

    # Save covariance Parquet artifact
    parquet_path, parquet_hash = persist_covariance_parquet(
        run_id=run_id,
        symbols=all_symbols,
        cov_matrix=cov_all,
    )

    artifact = AnalyticsArtifact(
        id=uuid4(),
        run_id=run_id,
        artifact_type="covariance_matrix_parquet",
        storage_path=parquet_path,
        content_hash=parquet_hash,
        details={
            "symbols": all_symbols,
            "dimensions": [n_all, n_all],
            "shrinkage_intensity": shrinkage_intensity,
        },
    )
    session.add(artifact)

    envelope = {
        "subject": f"portfolio:{portfolio.name}",
        "effective_time": eff_as_of.isoformat(),
        "method": "ledoit_wolf_covariance_risk_aggregation",
        "version": config_ver,
        "method_version": f"portfolio-risk-{config_ver}",
        "input_fingerprint": input_fp,
        "inputs_ref": {
            "portfolio_id": str(portfolio.id),
            "holding_count": len(active_holdings),
            "as_of": eff_as_of.isoformat(),
        },
        "lookback": {
            "window_size": window_size,
            "annualisation_factor": annualisation_factor,
        },
        "units": "annualised_volatility_pct",
        "thresholds": {
            "confidence_level_var": 0.95,
            "shrinkage_intensity": round(shrinkage_intensity, 6),
            "max_stale_days": 5,
        },
        "data_sufficiency": "sufficient" if not all_warnings else "partial",
        "confidence": {
            "score": 92.0 if not all_warnings else 78.0,
            "factors": {"coverage": 1.0, "freshness": 1.0},
            "caps": [],
        },
        "limitations": [
            (
                "PRISM provides descriptive risk and explanation, "
                "NOT price prediction and NOT investment advice."
            ),
            (
                "Linear aggregation approximation; buy-and-hold assumption "
                "without intra-window rebalancing."
            ),
            "Normal distribution assumption for parametric VaR and Expected Shortfall.",
            (
                "Correlation and MST structures are descriptive and non-causal "
                "per PRISM SRS Section 4."
            ),
            (
                "Single local user mode: no user-isolation authentication active "
                "(SRS NFR-7 privacy limitation)."
            ),
        ]
        + all_warnings,
        "computed_at": now_utc.isoformat(),
    }

    risk_run = PortfolioRiskRun(
        id=run_id,
        portfolio_id=portfolio.id,
        as_of=eff_as_of,
        config_version=config_ver,
        config_fingerprint=cfg_fingerprint,
        input_fingerprint=input_fp,
        window_size=window_size,
        annualisation_factor=Decimal(str(annualisation_factor)),
        portfolio_volatility=Decimal(str(metrics.portfolio_volatility)),
        portfolio_variance=Decimal(str(metrics.portfolio_variance)),
        portfolio_beta=Decimal(str(metrics.portfolio_beta))
        if metrics.portfolio_beta is not None
        else None,
        max_drawdown=Decimal(str(metrics.max_drawdown)),
        var_historical_95=Decimal(str(metrics.var_historical_95))
        if metrics.var_historical_95 is not None
        else None,
        var_parametric_95=Decimal(str(metrics.var_parametric_95))
        if metrics.var_parametric_95 is not None
        else None,
        es_historical_95=Decimal(str(metrics.es_historical_95))
        if metrics.es_historical_95 is not None
        else None,
        es_parametric_95=Decimal(str(metrics.es_parametric_95))
        if metrics.es_parametric_95 is not None
        else None,
        shrinkage_intensity=Decimal(str(shrinkage_intensity)),
        concentration_metrics=metrics.concentration_metrics,
        drawdown_series=metrics.drawdown_series,
        status="completed",
        data_sufficiency="sufficient" if not all_warnings else "partial",
        envelope=envelope,
        computed_at=now_utc,
    )
    session.add(risk_run)

    sym_to_sec_id = {h.symbol.upper(): h.security_id for h in active_holdings}
    db_contribs: list[PortfolioRiskContribution] = []
    for c in metrics.contributions:
        contrib = PortfolioRiskContribution(
            run_id=risk_run.id,
            security_id=sym_to_sec_id.get(c.symbol.upper()),
            symbol=c.symbol.upper(),
            weight=Decimal(str(c.weight)),
            asset_volatility=Decimal(str(c.asset_volatility)),
            marginal_contribution=Decimal(str(c.marginal_contribution)),
            percent_contribution=Decimal(str(c.percent_contribution)),
            beta=Decimal(str(c.beta)) if c.beta is not None else None,
            notes=c.notes,
        )
        session.add(contrib)
        db_contribs.append(contrib)

    session.commit()
    session.refresh(risk_run)

    return PortfolioRiskRunOut(
        id=risk_run.id,
        portfolio_id=risk_run.portfolio_id,
        as_of=risk_run.as_of,
        config_version=risk_run.config_version,
        config_fingerprint=risk_run.config_fingerprint,
        input_fingerprint=risk_run.input_fingerprint,
        window_size=risk_run.window_size,
        annualisation_factor=float(risk_run.annualisation_factor),
        portfolio_volatility=float(risk_run.portfolio_volatility),
        portfolio_variance=float(risk_run.portfolio_variance),
        portfolio_beta=float(risk_run.portfolio_beta)
        if risk_run.portfolio_beta is not None
        else None,
        max_drawdown=float(risk_run.max_drawdown),
        var_historical_95=float(risk_run.var_historical_95)
        if risk_run.var_historical_95 is not None
        else None,
        var_parametric_95=float(risk_run.var_parametric_95)
        if risk_run.var_parametric_95 is not None
        else None,
        es_historical_95=float(risk_run.es_historical_95)
        if risk_run.es_historical_95 is not None
        else None,
        es_parametric_95=float(risk_run.es_parametric_95)
        if risk_run.es_parametric_95 is not None
        else None,
        shrinkage_intensity=float(risk_run.shrinkage_intensity),
        concentration_metrics=risk_run.concentration_metrics,
        drawdown_series=[
            DrawdownPoint(
                date=d["date"],
                drawdown=d["drawdown"],
                portfolio_return=d["portfolio_return"],
            )
            for d in (risk_run.drawdown_series or [])
            if isinstance(d, dict)
        ],
        contributions=[
            RiskContributionOut(
                symbol=c.symbol,
                security_id=c.security_id,
                weight=float(c.weight),
                asset_volatility=float(c.asset_volatility),
                marginal_contribution=float(c.marginal_contribution),
                percent_contribution=float(c.percent_contribution),
                beta=float(c.beta) if c.beta is not None else None,
                notes=c.notes,
            )
            for c in db_contribs
        ],
        status=risk_run.status,
        data_sufficiency=risk_run.data_sufficiency,
        envelope=risk_run.envelope,
        computed_at=risk_run.computed_at,
    )


def get_latest_risk_run(session: Session, portfolio_id: UUID) -> PortfolioRiskRunOut:
    """Retrieve the latest risk run for a portfolio."""
    portfolio = session.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found",
        )

    run = session.scalar(
        select(PortfolioRiskRun)
        .where(
            PortfolioRiskRun.portfolio_id == portfolio_id,
            PortfolioRiskRun.status == "completed",
        )
        .order_by(PortfolioRiskRun.as_of.desc(), PortfolioRiskRun.computed_at.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No risk run found for portfolio {portfolio_id}",
        )

    contribs = session.scalars(
        select(PortfolioRiskContribution)
        .where(PortfolioRiskContribution.run_id == run.id)
        .order_by(PortfolioRiskContribution.percent_contribution.desc())
    ).all()

    return PortfolioRiskRunOut(
        id=run.id,
        portfolio_id=run.portfolio_id,
        as_of=run.as_of,
        config_version=run.config_version,
        config_fingerprint=run.config_fingerprint,
        input_fingerprint=run.input_fingerprint,
        window_size=run.window_size,
        annualisation_factor=float(run.annualisation_factor),
        portfolio_volatility=float(run.portfolio_volatility),
        portfolio_variance=float(run.portfolio_variance),
        portfolio_beta=float(run.portfolio_beta) if run.portfolio_beta is not None else None,
        max_drawdown=float(run.max_drawdown),
        var_historical_95=float(run.var_historical_95)
        if run.var_historical_95 is not None
        else None,
        var_parametric_95=float(run.var_parametric_95)
        if run.var_parametric_95 is not None
        else None,
        es_historical_95=float(run.es_historical_95) if run.es_historical_95 is not None else None,
        es_parametric_95=float(run.es_parametric_95) if run.es_parametric_95 is not None else None,
        shrinkage_intensity=float(run.shrinkage_intensity),
        concentration_metrics=dict(run.concentration_metrics or {}),
        drawdown_series=[
            DrawdownPoint(
                date=d["date"],
                drawdown=d["drawdown"],
                portfolio_return=d["portfolio_return"],
            )
            for d in (run.drawdown_series or [])
            if isinstance(d, dict)
        ],
        contributions=[
            RiskContributionOut(
                symbol=c.symbol,
                security_id=c.security_id,
                weight=float(c.weight),
                asset_volatility=float(c.asset_volatility),
                marginal_contribution=float(c.marginal_contribution),
                percent_contribution=float(c.percent_contribution),
                beta=float(c.beta) if c.beta is not None else None,
                notes=c.notes,
            )
            for c in contribs
        ],
        status=run.status,
        data_sufficiency=run.data_sufficiency,
        envelope=dict(run.envelope or {}),
        computed_at=run.computed_at,
    )


def get_latest_portfolio_risk_score(
    session: Session, portfolio_id: UUID
) -> PortfolioRiskScoreOut:
    """Aggregate latest stock scores and structural diversification for a portfolio."""
    portfolio = session.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Portfolio {portfolio_id} not found",
        )

    stock_run = session.scalars(
        select(ScoreRun)
        .where(ScoreRun.status == "completed")
        .order_by(desc(ScoreRun.completed_at))
        .limit(1)
    ).first()
    if stock_run is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="No completed stock risk score run is available",
        )

    holdings = session.scalars(
        select(PortfolioHolding)
        .where(
            PortfolioHolding.portfolio_id == portfolio_id,
            PortfolioHolding.as_of <= stock_run.as_of_date,
        )
        .order_by(desc(PortfolioHolding.as_of))
    ).all()
    if not holdings:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No portfolio holdings exist on or before the latest stock score date",
        )
    snapshot_date = holdings[0].as_of
    active_holdings = [holding for holding in holdings if holding.as_of == snapshot_date]

    stock_results = {
        row.security_id: row
        for row in session.scalars(
            select(StockRiskResult).where(StockRiskResult.run_id == stock_run.id)
        ).all()
    }
    scored_holdings: list[HoldingScoreInput] = []
    missing_holdings: list[str] = []
    total_weight = sum(max(0.0, float(holding.weight)) for holding in active_holdings)
    scored_weight = 0.0
    for holding in active_holdings:
        weight = max(0.0, float(holding.weight))
        if holding.symbol.upper() in {"CASH", "INR"}:
            scored_holdings.append(HoldingScoreInput(holding.symbol.upper(), weight, 0.0, 100.0))
            scored_weight += weight
            continue
        holding_result = (
            stock_results.get(holding.security_id) if holding.security_id is not None else None
        )
        if holding_result is None:
            missing_holdings.append(holding.symbol.upper())
            continue
        scored_holdings.append(
            HoldingScoreInput(
                symbol=holding.symbol.upper(),
                weight=weight,
                risk_score=float(holding_result.total_score),
                confidence=float(holding_result.confidence),
            )
        )
        scored_weight += weight

    if not scored_holdings:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="No current stock scores are available for the portfolio holdings",
        )

    diversification_pair = session.execute(
        select(DiversificationRun, PortfolioRiskRun)
        .join(
            PortfolioRiskRun,
            DiversificationRun.portfolio_risk_run_id == PortfolioRiskRun.id,
        )
        .where(
            PortfolioRiskRun.portfolio_id == portfolio_id,
            PortfolioRiskRun.as_of <= stock_run.as_of_date,
        )
        .order_by(desc(DiversificationRun.computed_at))
        .limit(1)
    ).first()
    diversification = diversification_pair[0] if diversification_pair is not None else None
    cluster_weights = dict(diversification.cluster_weights) if diversification is not None else {}
    numeric_cluster_weights = [
        float(value) for value in cluster_weights.values() if isinstance(value, (int, float))
    ]
    maximum_cluster_weight = max(numeric_cluster_weights) if numeric_cluster_weights else None
    enb_risk_entropy = (
        float(diversification.enb_risk_entropy) if diversification is not None else None
    )

    config_row = session.get(ModelConfig, stock_run.model_config_id)
    config = dict(config_row.configuration) if config_row is not None else {}
    portfolio_score = compute_portfolio_score(
        scored_holdings,
        enb_risk_entropy=enb_risk_entropy,
        maximum_cluster_weight=maximum_cluster_weight,
        config=config,
    )
    holding_coverage = scored_weight / total_weight if total_weight > 0 else 0.0
    coverage = portfolio_score.coverage * holding_coverage
    confidence = portfolio_score.confidence * holding_coverage
    limitations: list[str] = []
    if missing_holdings:
        limitations.append("Some portfolio holdings have no score in the latest stock run.")
    if diversification is None:
        limitations.append("No completed diversification run is available; structure is missing.")
    limitations.append(
        "Portfolio scores are descriptive risk summaries, not forecasts or investment advice."
    )

    return PortfolioRiskScoreOut(
        portfolio_id=portfolio_id,
        as_of=stock_run.as_of_date,
        stock_score_run_id=stock_run.id,
        diversification_run_id=diversification.id if diversification is not None else None,
        total_score=portfolio_score.total_score,
        holding_risk_score=portfolio_score.holding_risk_score,
        structure_score=portfolio_score.structure_score,
        structure_components=portfolio_score.structure_components,
        confidence=round(confidence, 2),
        weighted_holding_confidence=portfolio_score.weighted_holding_confidence,
        weakest_large_holding_confidence=portfolio_score.weakest_large_holding_confidence,
        coverage=round(coverage, 4),
        status=(
            "partial" if missing_holdings or portfolio_score.status == "partial" else "ok"
        ),
        missing_holdings=missing_holdings,
        contributions=portfolio_score.contributions,
        limitations=limitations,
        method_version="portfolio-risk-score-v2-draft",
        config_version=stock_run.config_version,
        computed_at=datetime.now(UTC),
    )


def get_or_run_portfolio_diversification(
    session: Session,
    portfolio_id: UUID,
) -> DiversificationResponse:
    """Retrieve or compute diversification analysis for the latest risk run of a portfolio."""
    # Find latest completed risk run
    risk_run = session.scalars(
        select(PortfolioRiskRun)
        .where(
            PortfolioRiskRun.portfolio_id == portfolio_id,
            PortfolioRiskRun.status == "completed",
        )
        .order_by(PortfolioRiskRun.computed_at.desc())
    ).first()

    if not risk_run:
        # Automatically compute risk run if not yet run
        risk_run_out = run_portfolio_risk(session, portfolio_id, RiskRunRequest())
        risk_run = session.get(PortfolioRiskRun, risk_run_out.id)
        if not risk_run:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Unable to establish risk run for portfolio {portfolio_id}",
            )

    from backend.app.portfolio.diversification import run_portfolio_diversification

    div_run = run_portfolio_diversification(session, risk_run.id)

    return DiversificationResponse(
        id=div_run.id,
        portfolio_risk_run_id=div_run.portfolio_risk_run_id,
        enb_eigen=float(div_run.enb_eigen),
        enb_risk_entropy=float(div_run.enb_risk_entropy),
        enb_default=float(div_run.enb_risk_entropy),
        enb_default_type="entropy",
        cluster_weights=dict(div_run.cluster_weights or {}),
        findings=dict(div_run.findings or {}),
        config_fingerprint=div_run.config_fingerprint,
        computed_at=div_run.computed_at,
    )


def run_shock_simulation(
    session: Session,
    portfolio_id: UUID,
    payload: ShockRequest,
) -> ShockScenarioResponse:
    """Execute shock scenario simulation on a portfolio."""
    from backend.app.portfolio.shock import simulate_portfolio_shock

    try:
        scenario, results, envelope = simulate_portfolio_shock(
            session=session,
            portfolio_id=portfolio_id,
            shocked_symbol=payload.symbol,
            shock_pct=payload.shock_pct,
            method=payload.method,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    results_out = [
        ShockResultOut(
            symbol=str(r.method_detail.get("symbol", "")),
            security_id=r.security_id,
            weight=float(r.weight),
            estimated_impact_pct=float(r.estimated_impact_pct),
            contribution_pct=float(r.contribution_pct),
            method_detail=dict(r.method_detail or {}),
        )
        for r in results
    ]

    return ShockScenarioResponse(
        id=scenario.id,
        portfolio_id=scenario.portfolio_id,
        shocked_security_id=scenario.shocked_security_id,
        shocked_symbol=payload.symbol.upper(),
        shock_pct=float(scenario.shock_pct),
        method_version=scenario.method_version,
        portfolio_impact_pct=float(envelope["portfolio_impact_pct"]),
        banner=str(envelope["banner"]),
        assumptions=list(envelope.get("assumptions", [])),
        results=results_out,
        created_at=scenario.created_at,
    )


def get_shock_scenario(
    session: Session,
    portfolio_id: UUID,
    scenario_id: UUID,
) -> ShockScenarioResponse:
    """Retrieve an existing shock scenario and its results."""
    from backend.app.db.models import ShockResult, ShockScenario

    scenario = session.get(ShockScenario, scenario_id)
    if not scenario or scenario.portfolio_id != portfolio_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Shock scenario {scenario_id} not found for portfolio {portfolio_id}.",
        )

    results = session.scalars(
        select(ShockResult)
        .where(ShockResult.scenario_id == scenario_id)
        .order_by(ShockResult.contribution_pct.asc())
    ).all()

    # Total impact
    total_impact = sum(float(r.contribution_pct) for r in results)

    # Shocked symbol
    from backend.app.db.models import SecurityAlias

    if scenario.shocked_security_id:
        alias_stmt = select(SecurityAlias.symbol).where(
            SecurityAlias.security_id == scenario.shocked_security_id
        )
        shocked_sym_val = session.scalars(alias_stmt).first()
        shocked_symbol = shocked_sym_val or "SELECTED"
    else:
        shocked_symbol = "SELECTED"

    results_out = [
        ShockResultOut(
            symbol=str(r.method_detail.get("symbol", "")),
            security_id=r.security_id,
            weight=float(r.weight),
            estimated_impact_pct=float(r.estimated_impact_pct),
            contribution_pct=float(r.contribution_pct),
            method_detail=dict(r.method_detail or {}),
        )
        for r in results
    ]

    assumptions = [
        "Linear co-movement estimated over trailing trading window is assumed constant.",
        "No liquidity feedback or execution slippage cascades.",
        "Covariance stability during hypothetical shock scenario.",
        f"Isolated shock to {shocked_symbol} without contemporaneous independent shocks.",
    ]

    return ShockScenarioResponse(
        id=scenario.id,
        portfolio_id=scenario.portfolio_id,
        shocked_security_id=scenario.shocked_security_id,
        shocked_symbol=shocked_symbol,
        shock_pct=float(scenario.shock_pct),
        method_version=scenario.method_version,
        portfolio_impact_pct=round(total_impact, 4),
        banner="Scenario estimate, not a prediction",
        assumptions=assumptions,
        results=results_out,
        created_at=scenario.created_at,
    )
