"""Point-in-time data loaders and mathematical helpers for risk components (D4)."""

from datetime import date, timedelta
from uuid import UUID

from typing import cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sqlalchemy import select

from backend.app.db.models import (
    BenchmarkDefinition,
    BenchmarkSeries,
    PriceDailyAdjusted,
    PriceDailyRaw,
)
from backend.app.risk_score.components.base import RiskContext


def get_adjusted_prices_map(
    context: RiskContext,
    universe: list[tuple[UUID, str, str]],
    lookback_days: int = 365,
) -> dict[UUID, pd.Series]:
    """Retrieve point-in-time adjusted close price series for all universe securities."""
    cache_key = f"adjusted_prices_{lookback_days}"
    if cache_key in context.cache:
        return cast(dict[UUID, pd.Series], context.cache[cache_key])

    session = context.session
    sec_ids = [u[0] for u in universe]
    min_date = context.as_of - timedelta(days=int(lookback_days * 1.6))

    rows = session.scalars(
        select(PriceDailyAdjusted)
        .where(
            PriceDailyAdjusted.security_id.in_(sec_ids),
            PriceDailyAdjusted.trade_date <= context.as_of,
            PriceDailyAdjusted.trade_date >= min_date,
            PriceDailyAdjusted.computed_at <= context.data_cutoff,
        )
        .order_by(PriceDailyAdjusted.security_id, PriceDailyAdjusted.trade_date)
    ).all()

    series_map: dict[UUID, dict[date, float]] = {s_id: {} for s_id in sec_ids}
    for r in rows:
        series_map[r.security_id][r.trade_date] = float(r.adjusted_close)

    result = {
        s_id: pd.Series(dates_dict).sort_index()
        for s_id, dates_dict in series_map.items()
    }
    context.cache[cache_key] = result
    return result


def get_raw_prices_map(
    context: RiskContext,
    universe: list[tuple[UUID, str, str]],
    lookback_days: int = 120,
) -> dict[UUID, pd.DataFrame]:
    """Retrieve point-in-time raw price and volume records."""
    cache_key = f"raw_prices_{lookback_days}"
    if cache_key in context.cache:
        return cast(dict[UUID, pd.DataFrame], context.cache[cache_key])

    session = context.session
    sec_ids = [u[0] for u in universe]
    min_date = context.as_of - timedelta(days=int(lookback_days * 1.6))

    rows = session.scalars(
        select(PriceDailyRaw)
        .where(
            PriceDailyRaw.security_id.in_(sec_ids),
            PriceDailyRaw.trade_date <= context.as_of,
            PriceDailyRaw.trade_date >= min_date,
            PriceDailyRaw.ingested_at <= context.data_cutoff,
        )
        .order_by(PriceDailyRaw.security_id, PriceDailyRaw.trade_date)
    ).all()

    df_map: dict[UUID, list[dict[str, object]]] = {s_id: [] for s_id in sec_ids}
    for r in rows:
        df_map[r.security_id].append(
            {
                "trade_date": r.trade_date,
                "close": float(r.close),
                "volume": int(r.volume) if r.volume is not None else 0,
            }
        )

    result = {
        s_id: pd.DataFrame(records).set_index("trade_date").sort_index()
        if records
        else pd.DataFrame()
        for s_id, records in df_map.items()
    }
    context.cache[cache_key] = result
    return result


def get_benchmark_returns(
    context: RiskContext,
    benchmark_name: str = "NIFTY 200",
    lookback_days: int = 365,
) -> pd.Series:
    """Retrieve point-in-time benchmark log returns series."""
    cache_key = f"benchmark_returns_{benchmark_name}_{lookback_days}"
    if cache_key in context.cache:
        return context.cache[cache_key]

    session = context.session
    min_date = context.as_of - timedelta(days=int(lookback_days * 1.6))

    bench_id = session.scalar(
        select(BenchmarkDefinition.id).where(BenchmarkDefinition.name == benchmark_name)
    )

    series = pd.Series(dtype=float)
    if bench_id is not None:
        rows = session.scalars(
            select(BenchmarkSeries)
            .where(
                BenchmarkSeries.benchmark_id == bench_id,
                BenchmarkSeries.trade_date <= context.as_of,
                BenchmarkSeries.trade_date >= min_date,
                BenchmarkSeries.ingested_at <= context.data_cutoff,
            )
            .order_by(BenchmarkSeries.trade_date)
        ).all()
        if rows:
            prices = pd.Series(
                {r.trade_date: float(r.close) for r in rows}
            ).sort_index()
            series = np.log(prices / prices.shift(1)).dropna()

    context.cache[cache_key] = series
    return series
