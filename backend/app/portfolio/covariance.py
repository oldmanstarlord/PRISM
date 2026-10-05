"""Returns panel construction, Ledoit-Wolf covariance shrinkage, and Parquet artifact storage."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import PriceDailyAdjusted


def get_adjusted_returns_panel(
    session: Session,
    security_ids: list[UUID],
    as_of: date,
    window_size: int = 250,
) -> tuple[pd.DataFrame, list[str]]:
    """Fetch daily adjusted close prices for given securities and compute log returns.

    Lookback is strictly point-in-time (trade_date <= as_of).
    Returns:
        (returns_df, warnings) where columns are str(security_id) or ticker symbol,
        index is trade_date, values are log returns r_{i, t} = ln(P_{i, t} / P_{i, t-1}).
    """
    warnings: list[str] = []
    if not security_ids:
        return pd.DataFrame(), warnings

    # Fetch unique trading dates up to as_of
    date_stmt = (
        select(PriceDailyAdjusted.trade_date)
        .where(
            PriceDailyAdjusted.security_id.in_(security_ids),
            PriceDailyAdjusted.trade_date <= as_of,
        )
        .distinct()
        .order_by(PriceDailyAdjusted.trade_date.desc())
        .limit(window_size + 1)
    )
    trading_dates = sorted(session.scalars(date_stmt).all())

    if len(trading_dates) < 2:
        warnings.append(
            f"Insufficient price history for portfolio assets before {as_of} "
            f"(found {len(trading_dates)} dates, minimum 2 required)."
        )
        return pd.DataFrame(), warnings

    # Fetch price records
    price_stmt = (
        select(
            PriceDailyAdjusted.security_id,
            PriceDailyAdjusted.trade_date,
            PriceDailyAdjusted.adjusted_close,
        )
        .where(
            PriceDailyAdjusted.security_id.in_(security_ids),
            PriceDailyAdjusted.trade_date.in_(trading_dates),
        )
        .order_by(PriceDailyAdjusted.trade_date.asc())
    )

    rows = session.execute(price_stmt).all()
    if not rows:
        return pd.DataFrame(), warnings

    # Pivot into DataFrame (trade_date x security_id)
    price_data: dict[UUID, dict[date, float]] = {sid: {} for sid in security_ids}
    for sid, tdate, close_adj in rows:
        price_data[sid][tdate] = float(close_adj)

    price_df = pd.DataFrame(price_data, index=trading_dates)

    # Check for missing values
    missing_counts = price_df.isna().sum()
    for sid, m_count in missing_counts.items():
        if m_count > 0:
            warnings.append(
                f"Security {sid} missing {m_count} of {len(trading_dates)} price observations; "
                "forward-filled to preserve point-in-time returns alignment."
            )

    # Forward fill then backward fill to prevent NaN breaks
    price_df = price_df.ffill().bfill()

    # Compute log returns: r_{i, t} = ln(P_t / P_{t-1})
    returns_df = np.log(price_df / price_df.shift(1)).iloc[1:]

    return returns_df, warnings


def compute_covariance(
    returns_df: pd.DataFrame,
    shrinkage_override: float | None = None,
    annualise: bool = True,
    annualisation_factor: float = 252.0,
) -> tuple[np.ndarray, float]:
    """Compute sample or Ledoit-Wolf shrunk covariance matrix.

    If shrinkage_override == 0.0, uses unbiased sample covariance (ddof=1).
    Otherwise fits sklearn LedoitWolf.
    Returns:
        (cov_matrix, shrinkage_intensity)
    """
    x = returns_df.values
    n_samples, n_features = x.shape

    if n_samples < 2 or n_features == 0:
        empty = np.zeros((n_features, n_features), dtype=np.float64)
        return empty, 0.0

    if shrinkage_override is not None and abs(shrinkage_override) < 1e-9:
        # Sample covariance
        cov_daily = np.cov(x, rowvar=False, ddof=1)
        if n_features == 1:
            cov_daily = np.array([[float(cov_daily)]])
        shrinkage_intensity = 0.0
    else:
        try:
            lw = LedoitWolf(assume_centered=False)
            lw.fit(x)
            cov_daily = lw.covariance_
            shrinkage_intensity = float(lw.shrinkage_)
        except Exception:
            # Fallback to sample covariance if LedoitWolf fails (e.g. constant series)
            cov_daily = np.cov(x, rowvar=False, ddof=1)
            if n_features == 1:
                cov_daily = np.array([[float(cov_daily)]])
            shrinkage_intensity = 0.0

    factor = annualisation_factor if annualise else 1.0
    cov_matrix = cov_daily * factor
    return cov_matrix, shrinkage_intensity


def persist_covariance_parquet(
    run_id: UUID,
    symbols: list[str],
    cov_matrix: np.ndarray,
    base_dir: str = "data/processed",
) -> tuple[str, str]:
    """Serialize covariance matrix as Parquet file and compute SHA-256 hash.

    Returns:
        (relative_storage_path, content_hash)
    """
    target_dir = Path(base_dir) / "covariances"
    target_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"cov_{run_id}.parquet"
    target_path = target_dir / file_name

    df = pd.DataFrame(cov_matrix, index=symbols, columns=symbols)
    df.to_parquet(target_path)

    # Compute SHA-256
    with open(target_path, "rb") as f:
        file_bytes = f.read()
    content_hash = hashlib.sha256(file_bytes).hexdigest()

    rel_path = f"{base_dir}/covariances/{file_name}"
    return rel_path, content_hash
