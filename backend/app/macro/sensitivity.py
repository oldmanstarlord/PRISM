"""Sector macroeconomic sensitivity regression engine (FR-D3, FR-D4, FR-D6)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import numpy as np
from scipy import stats
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    MacroObservation,
    MacroSeriesDefinition,
    ModelConfig,
    PriceDailyAdjusted,
    SectorMacroSensitivity,
    Security,
)


@dataclass(frozen=True)
class RegressionResult:
    """Statistical outcome of OLS sensitivity regression."""

    industry: str
    series_key: str
    window_end: date
    beta: float
    t_stat: float
    n_obs: int
    p_value: float
    is_significant: bool


def compute_ols_sensitivity(
    x_changes: list[float],
    y_returns: list[float],
    min_obs: int = 30,
    t_crit: float = 1.96,
) -> tuple[float, float, int, float, bool]:
    """Compute pure single-variable OLS regression.

    Returns:
        (beta, t_stat, n_obs, p_value, is_significant)
    """
    n = len(x_changes)
    if n < min_obs or len(y_returns) != n:
        return 0.0, 0.0, n, 1.0, False

    x_arr = np.array(x_changes, dtype=float)
    y_arr = np.array(y_returns, dtype=float)

    # Filter any NaNs or infinities
    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_clean = x_arr[mask]
    y_clean = y_arr[mask]
    n_clean = len(x_clean)

    if n_clean < min_obs:
        return 0.0, 0.0, n_clean, 1.0, False

    var_x = float(np.var(x_clean, ddof=1))
    if var_x < 1e-12:
        return 0.0, 0.0, n_clean, 1.0, False

    cov_xy = float(np.cov(x_clean, y_clean, ddof=1)[0, 1])
    beta = cov_xy / var_x
    alpha = float(np.mean(y_clean) - beta * np.mean(x_clean))

    residuals = y_clean - (alpha + beta * x_clean)
    rss = float(np.sum(residuals**2))
    df = n_clean - 2
    if df <= 0:
        return beta, 0.0, n_clean, 1.0, False

    s_err = math.sqrt(rss / df)
    se_beta = s_err / (math.sqrt(var_x * (n_clean - 1)))

    if se_beta < 1e-12:
        t_stat = 0.0
        p_val = 1.0
    else:
        t_stat = float(beta / se_beta)
        p_val = float(2.0 * stats.t.sf(abs(t_stat), df=df))

    is_sig = bool(abs(t_stat) >= t_crit and p_val <= 0.05)
    return float(beta), float(t_stat), n_clean, float(p_val), is_sig


def calculate_sector_macro_sensitivities(
    session: Session,
    as_of: date,
    cutoff: datetime | None = None,
    config_version: str = "1.0.0",
    force: bool = False,
) -> list[SectorMacroSensitivity]:
    """Calculate and persist rolling macro sensitivities for all industries."""
    cutoff_time = cutoff or datetime.combine(as_of, datetime.max.time(), tzinfo=UTC)

    # 1. Load config
    cfg_row = session.scalars(
        select(ModelConfig).where(
            ModelConfig.config_key == "macro_regime_sensitivity",
            ModelConfig.version == config_version,
        )
    ).first()

    config: dict[str, Any] = (
        cfg_row.configuration if cfg_row and isinstance(cfg_row.configuration, dict) else {}
    )
    lookback_days = int(config.get("sensitivity_lookback_days", 63))
    min_obs = int(config.get("min_sensitivity_observations", 30))
    t_crit = float(config.get("t_stat_significance_threshold", 1.96))

    # 2. Check for existing runs
    existing = session.scalars(
        select(SectorMacroSensitivity).where(
            SectorMacroSensitivity.window_end == as_of,
            SectorMacroSensitivity.config_version == config_version,
        )
    ).all()

    if existing and not force:
        return list(existing)

    # 3. Query distinct industries of active securities
    industries = session.scalars(
        select(Security.industry)
        .where(
            Security.is_active == True,  # noqa: E712
            Security.industry.is_not(None),
        )
        .distinct()
    ).all()
    clean_industries = [ind for ind in industries if ind and ind.strip()]

    # 4. Load macro observations for active series
    active_series = session.scalars(
        select(MacroSeriesDefinition.series_key).where(
            MacroSeriesDefinition.is_active == True  # noqa: E712
        )
    ).all()

    min_calendar_date = as_of - timedelta(days=int(lookback_days * 2.2))

    macro_by_series: dict[str, dict[date, float]] = {}
    for s_key in active_series:
        obs_rows = session.execute(
            select(MacroObservation.obs_date, MacroObservation.value)
            .where(
                MacroObservation.series_key == s_key,
                MacroObservation.obs_date <= as_of,
                MacroObservation.obs_date >= min_calendar_date,
                MacroObservation.published_at <= cutoff_time,
                MacroObservation.source == "YAHOO",
            )
            .order_by(MacroObservation.obs_date.asc())
        ).all()
        macro_by_series[s_key] = {d: float(v) for d, v in obs_rows}

    # Compute daily macro changes:
    # Crude oil, USD/INR, VIX -> relative return
    # Yield -> absolute change
    # Net flows -> standardized flow
    macro_changes_by_series: dict[str, dict[date, float]] = {}
    for s_key, date_val in macro_by_series.items():
        sorted_dates = sorted(date_val.keys())
        changes: dict[date, float] = {}
        for i in range(1, len(sorted_dates)):
            d_prev = sorted_dates[i - 1]
            d_cur = sorted_dates[i]
            v_prev = date_val[d_prev]
            v_cur = date_val[d_cur]

            if s_key in ("in_10y_yield", "fii_dii_net_flows"):
                delta = v_cur - v_prev
            else:
                delta = (v_cur - v_prev) / v_prev if abs(v_prev) > 1e-8 else 0.0
            changes[d_cur] = delta
        macro_changes_by_series[s_key] = changes

    # 5. Load industry equal-weight daily returns
    # Fetch industry-level daily average adjusted close
    industry_avg_prices = session.execute(
        select(
            Security.industry,
            PriceDailyAdjusted.trade_date,
            func.avg(PriceDailyAdjusted.adjusted_close).label("avg_close"),
        )
        .join(PriceDailyAdjusted, PriceDailyAdjusted.security_id == Security.id)
        .where(
            Security.is_active == True,  # noqa: E712
            Security.industry.is_not(None),
            PriceDailyAdjusted.trade_date <= as_of,
            PriceDailyAdjusted.trade_date >= min_calendar_date,
            PriceDailyAdjusted.computed_at <= cutoff_time,
        )
        .group_by(Security.industry, PriceDailyAdjusted.trade_date)
        .order_by(Security.industry, PriceDailyAdjusted.trade_date.asc())
    ).all()

    industry_daily_returns: dict[str, dict[date, float]] = {}
    raw_ind_series: dict[str, list[tuple[date, float]]] = {}
    for ind, d, p in industry_avg_prices:
        if ind and p is not None:
            raw_ind_series.setdefault(ind, []).append((d, float(p)))

    for ind, date_price_list in raw_ind_series.items():
        rets: dict[date, float] = {}
        for i in range(1, len(date_price_list)):
            d_cur, p_cur = date_price_list[i]
            _, p_prev = date_price_list[i - 1]
            if p_prev > 0:
                rets[d_cur] = math.log(p_cur / p_prev)
        industry_daily_returns[ind] = rets

    # 6. Run regression for each (industry, series_key)
    results: list[SectorMacroSensitivity] = []
    existing_map = {(r.industry, r.series_key): r for r in existing} if existing else {}

    now = datetime.now(UTC)

    for ind in clean_industries:
        ind_rets = industry_daily_returns.get(ind, {})
        for s_key in active_series:
            s_changes = macro_changes_by_series.get(s_key, {})

            # Match dates on trailing lookback window
            common_dates = sorted(set(ind_rets.keys()) & set(s_changes.keys()))
            if len(common_dates) > lookback_days:
                common_dates = common_dates[-lookback_days:]

            x_vals = [s_changes[d] for d in common_dates]
            y_vals = [ind_rets[d] for d in common_dates]

            beta, t_stat, n_clean, p_val, is_sig = compute_ols_sensitivity(
                x_changes=x_vals,
                y_returns=y_vals,
                min_obs=min_obs,
                t_crit=t_crit,
            )

            # Persist or update row
            row = existing_map.get((ind, s_key))
            if row is not None:
                row.beta = round(beta, 6)
                row.t_stat = round(t_stat, 4)
                row.n_obs = n_clean
                row.p_value = round(p_val, 6)
                row.is_significant = is_sig
            else:
                row = SectorMacroSensitivity(
                    id=uuid4(),
                    industry=ind,
                    series_key=s_key,
                    window_end=as_of,
                    beta=round(beta, 6),
                    t_stat=round(t_stat, 4),
                    n_obs=n_clean,
                    p_value=round(p_val, 6),
                    is_significant=is_sig,
                    config_version=config_version,
                    created_at=now,
                )
                session.add(row)

            results.append(row)

    session.commit()
    return results
