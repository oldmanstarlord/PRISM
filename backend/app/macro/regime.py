"""Rule-based market regime classification engine with hysteresis (FR-F4, D1, D3, D4)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import numpy as np
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    MacroObservation,
    MarketRegime,
    ModelConfig,
    PriceDailyAdjusted,
)


@dataclass(frozen=True)
class RegimeClassificationResult:
    """Evaluated market regime with point-in-time features."""

    as_of: date
    regime: str  # "calm" | "trending" | "stressed"
    features: dict[str, Any]
    config_version: str
    is_new: bool = True


DEFAULT_REGIME_CONFIG: dict[str, Any] = {
    "rv_lookback_days": 21,
    "rv_history_days": 252,
    "correlation_lookback_days": 63,
    "correlation_history_days": 252,
    "vix_calm_threshold": 14.5,
    "vix_trending_threshold": 16.5,
    "vix_stressed_threshold": 22.0,
    "vix_exit_stressed_threshold": 19.0,
    "vol_pctl_calm_entry": 40.0,
    "vol_pctl_trending_entry": 45.0,
    "vol_pctl_stressed_entry": 75.0,
    "vol_pctl_exit_calm": 35.0,
    "vol_pctl_exit_stressed": 65.0,
    "corr_pctl_calm_entry": 40.0,
    "corr_pctl_trending_entry": 45.0,
    "corr_pctl_stressed_entry": 75.0,
    "corr_pctl_exit_calm": 35.0,
    "corr_pctl_exit_stressed": 65.0,
    "regime_multipliers": {
        "calm": 1.0,
        "trending": 1.25,
        "stressed": 1.5,
    },
}


def compute_empirical_percentile(value: float, history: list[float]) -> float:
    """Compute empirical percentile rank in [0, 100]."""
    if not history:
        return 50.0
    arr = np.array(history, dtype=float)
    less = np.sum(arr < value)
    equal = np.sum(arr == value)
    return float(100.0 * (less + 0.5 * equal) / len(arr))


def evaluate_regime_state(
    vol_pctl: float,
    corr_pctl: float,
    vix: float | None,
    prior_regime: str | None,
    config: dict[str, Any],
) -> tuple[str, str]:
    """Pure hysteresis state machine transition logic.

    Returns:
        (new_regime, transition_reason)
    """
    vix_stressed = config.get("vix_stressed_threshold", 22.0)
    vix_trending = config.get("vix_trending_threshold", 16.5)
    vix_calm = config.get("vix_calm_threshold", 14.5)
    vix_exit_stressed = config.get("vix_exit_stressed_threshold", 19.0)

    vol_stressed = config.get("vol_pctl_stressed_entry", 75.0)
    vol_trending = config.get("vol_pctl_trending_entry", 45.0)
    vol_exit_calm = config.get("vol_pctl_exit_calm", 35.0)
    vol_exit_stressed = config.get("vol_pctl_exit_stressed", 65.0)

    corr_stressed = config.get("corr_pctl_stressed_entry", 75.0)
    corr_trending = config.get("corr_pctl_trending_entry", 45.0)
    corr_exit_calm = config.get("corr_pctl_exit_calm", 35.0)
    corr_exit_stressed = config.get("corr_pctl_exit_stressed", 65.0)

    # Condition to enter stressed
    is_stressed_spike = (
        vol_pctl >= vol_stressed
        or corr_pctl >= corr_stressed
        or (vix is not None and vix >= vix_stressed)
    )

    current = prior_regime or "calm"

    if current == "stressed":
        if is_stressed_spike:
            return "stressed", "sustained_stress_spike"
        # Hysteresis exit checks:
        # 1. Exit directly to calm if both vol and corr drop below exit_calm thresholds
        can_calm = (
            vol_pctl < vol_exit_calm
            and corr_pctl < corr_exit_calm
            and (vix is None or vix < vix_calm)
        )
        if can_calm:
            return "calm", "stress_resolved_to_calm"

        # 2. Exit to trending if metrics subside below exit_stressed thresholds
        can_trending = (
            vol_pctl < vol_exit_stressed
            and corr_pctl < corr_exit_stressed
            and (vix is None or vix < vix_exit_stressed)
        )
        if can_trending:
            return "trending", "stress_subsided_to_trending"

        return "stressed", "hysteresis_lock_in_stress"

    elif current == "trending":
        if is_stressed_spike:
            return "stressed", "vol_or_corr_stressed_breach"
        can_calm = (
            vol_pctl < vol_exit_calm
            and corr_pctl < corr_exit_calm
            and (vix is None or vix < vix_calm)
        )
        if can_calm:
            return "calm", "dispersion_normalised_to_calm"
        return "trending", "sustained_trending"

    else:  # current == "calm"
        if is_stressed_spike:
            return "stressed", "vol_or_corr_stressed_breach"
        can_trending = (
            vol_pctl >= vol_trending
            or corr_pctl >= corr_trending
            or (vix is not None and vix >= vix_trending)
        )
        if can_trending:
            return "trending", "vol_or_corr_trending_breach"
        return "calm", "sustained_calm"


def classify_market_regime(
    session: Session,
    as_of: date,
    cutoff: datetime | None = None,
    config_version: str = "1.0.0",
    force: bool = False,
) -> RegimeClassificationResult:
    """Point-in-time calculation and persistence of market regime."""
    cutoff_time = cutoff or datetime.combine(as_of, datetime.max.time(), tzinfo=UTC)

    # 1. Check existing record
    existing = session.scalars(
        select(MarketRegime).where(
            MarketRegime.as_of == as_of,
            MarketRegime.config_version == config_version,
        )
    ).first()

    if existing and not force:
        return RegimeClassificationResult(
            as_of=existing.as_of,
            regime=existing.regime,
            features=existing.features,
            config_version=existing.config_version,
            is_new=False,
        )

    # 2. Load model config
    cfg_row = session.scalars(
        select(ModelConfig).where(
            ModelConfig.config_key == "macro_regime_sensitivity",
            ModelConfig.version == config_version,
        )
    ).first()

    config = (
        cfg_row.configuration
        if cfg_row and isinstance(cfg_row.configuration, dict)
        else DEFAULT_REGIME_CONFIG
    )

    # 3. Load trailing India VIX point-in-time
    vix_obs = session.scalars(
        select(MacroObservation)
        .where(
            MacroObservation.series_key == "india_vix",
            MacroObservation.source == "YAHOO",
            MacroObservation.obs_date <= as_of,
            MacroObservation.published_at <= cutoff_time,
        )
        .order_by(desc(MacroObservation.obs_date))
        .limit(1)
    ).first()
    vix_val = vix_obs.value if vix_obs else None

    # 4. Compute market realized volatility and history
    min_trade_date = as_of - timedelta(days=450)
    market_rows = session.execute(
        select(
            PriceDailyAdjusted.trade_date,
            func.avg(PriceDailyAdjusted.adjusted_close).label("avg_close"),
        )
        .where(
            PriceDailyAdjusted.trade_date <= as_of,
            PriceDailyAdjusted.trade_date >= min_trade_date,
            PriceDailyAdjusted.computed_at <= cutoff_time,
        )
        .group_by(PriceDailyAdjusted.trade_date)
        .order_by(PriceDailyAdjusted.trade_date.asc())
    ).all()

    sorted_dates: list[date] = []
    avg_prices: list[float] = []
    for d, p in market_rows:
        if p is not None:
            sorted_dates.append(d)
            avg_prices.append(float(p))

    # Build market return series
    daily_returns: list[float] = []
    if len(avg_prices) >= 2:
        for i in range(1, len(avg_prices)):
            prev_p = avg_prices[i - 1]
            cur_p = avg_prices[i]
            ret = math.log(cur_p / prev_p) if prev_p > 0 else 0.0
            daily_returns.append(ret)

    rv_lookback = int(str(config.get("rv_lookback_days", 21)))
    rv_history_days = int(str(config.get("rv_history_days", 252)))

    current_rv = 0.15  # Default baseline annualised volatility 15%
    vol_pctl = 50.0

    if len(daily_returns) >= rv_lookback:
        # Annualized 21-day rolling volatility: std * sqrt(252)
        recent_window = daily_returns[-rv_lookback:]
        current_rv = float(np.std(recent_window, ddof=1) * math.sqrt(252))

        # Build historical RVs over history window
        history_rvs: list[float] = []
        max_start = max(0, len(daily_returns) - rv_history_days - rv_lookback)
        for i in range(max_start, len(daily_returns) - rv_lookback + 1):
            w = daily_returns[i : i + rv_lookback]
            if len(w) == rv_lookback:
                history_rvs.append(float(np.std(w, ddof=1) * math.sqrt(252)))

        vol_pctl = compute_empirical_percentile(current_rv, history_rvs)

    # 5. Average pairwise correlation proxy & percentile
    # If VIX is available, incorporate VIX percentile into correlation proxy
    avg_corr = 0.35
    corr_pctl = 50.0

    if vix_val is not None:
        # Load historical VIX to compute correlation proxy percentile
        vix_history = session.scalars(
            select(MacroObservation.value)
            .where(
                MacroObservation.series_key == "india_vix",
                MacroObservation.source == "YAHOO",
                MacroObservation.obs_date <= as_of,
                MacroObservation.published_at <= cutoff_time,
            )
            .order_by(desc(MacroObservation.obs_date))
            .limit(252)
        ).all()
        corr_pctl = compute_empirical_percentile(vix_val, [float(v) for v in vix_history])
        avg_corr = float(0.20 + 0.35 * (corr_pctl / 100.0))
    else:
        corr_pctl = vol_pctl

    # 6. Fetch prior regime
    prior_row = session.scalars(
        select(MarketRegime)
        .where(
            MarketRegime.as_of < as_of,
            MarketRegime.config_version == config_version,
        )
        .order_by(desc(MarketRegime.as_of))
        .limit(1)
    ).first()
    prior_regime = prior_row.regime if prior_row else None

    # 7. Evaluate regime state
    regime, reason = evaluate_regime_state(
        vol_pctl=vol_pctl,
        corr_pctl=corr_pctl,
        vix=vix_val,
        prior_regime=prior_regime,
        config=config,
    )

    reg_mults = config.get("regime_multipliers", {})
    multiplier = float(reg_mults.get(regime, 1.0)) if isinstance(reg_mults, dict) else 1.0

    features: dict[str, Any] = {
        "rv_annualized": round(current_rv, 4),
        "vol_percentile": round(vol_pctl, 2),
        "avg_correlation": round(avg_corr, 4),
        "corr_percentile": round(corr_pctl, 2),
        "india_vix": round(vix_val, 2) if vix_val is not None else None,
        "prior_regime": prior_regime,
        "transition_reason": reason,
        "regime_multiplier": multiplier,
    }

    # 8. Persist to database
    if existing:
        existing.regime = regime
        existing.features = features
    else:
        new_row = MarketRegime(
            id=uuid4(),
            as_of=as_of,
            regime=regime,
            features=features,
            config_version=config_version,
            created_at=datetime.now(UTC),
        )
        session.add(new_row)

    session.commit()

    return RegimeClassificationResult(
        as_of=as_of,
        regime=regime,
        features=features,
        config_version=config_version,
        is_new=True,
    )
