"""FastAPI router exposing market data and live quotes powered by yfinance."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import DataCoverageRun, StockMetricDaily
from backend.app.db.session import get_session
from backend.app.market_data.foundation import coverage_payload
from backend.app.market_data.live_service import (
    fetch_batch_quotes,
    fetch_benchmark,
    fetch_historical_ohlcv,
    fetch_quote,
    get_market_data_health,
)
from backend.app.market_data.metrics import METHODOLOGY_VERSION

router = APIRouter(prefix="/market-data", tags=["market data"])
DatabaseSession = Annotated[Session, Depends(get_session)]


class BatchQuotesRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=100)
    force_refresh: bool = False


@router.get("/quote/{symbol}")
def get_quote(
    symbol: str,
    session: DatabaseSession,
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Retrieve quote and sector metadata for a single stock symbol."""
    quote = fetch_quote(symbol, session=session, force_refresh=force_refresh)
    return quote.to_dict()


@router.post("/quotes")
def get_batch_quotes(
    payload: BatchQuotesRequest,
    session: DatabaseSession,
) -> dict[str, Any]:
    """Retrieve live quotes for a list of portfolio symbols and market benchmark."""
    return fetch_batch_quotes(
        payload.symbols,
        session=session,
        force_refresh=payload.force_refresh,
    )


@router.get("/benchmark")
def get_benchmark(
    session: DatabaseSession,
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Retrieve current level and day change for the NIFTY 50 benchmark."""
    benchmark = fetch_benchmark(session=session, force_refresh=force_refresh)
    return benchmark.to_dict()


@router.get("/history/{symbol}")
def get_history(
    symbol: str,
    session: DatabaseSession,
    period: str = Query(default="1mo", pattern="^(5d|1mo|3mo|6mo|1y|2y|5y|max)$"),
    interval: str = Query(default="1d", pattern="^(1d|1wk|1mo)$"),
    force_refresh: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """Retrieve historical daily OHLCV bars for charts and risk models."""
    return fetch_historical_ohlcv(
        symbol,
        period=period,
        interval=interval,
        session=session,
        force_refresh=force_refresh,
    )


@router.get("/health")
def get_health(session: DatabaseSession) -> dict[str, Any]:
    """Report provider health, database coverage, benchmark status, and limitations."""
    return get_market_data_health(session)


@router.get("/coverage/latest")
def get_latest_coverage(session: DatabaseSession) -> dict[str, Any]:
    """Return the most recently published all-universe coverage report."""
    row = session.scalar(
        select(DataCoverageRun).order_by(desc(DataCoverageRun.last_update_time)).limit(1)
    )
    if row is None:
        return {
            "status": "unavailable",
            "reason": "no_data_coverage_run_has_been_published",
            "excluded_symbols": [],
        }
    return coverage_payload(row)


@router.get("/stock-metrics/latest")
def get_latest_stock_metrics(session: DatabaseSession) -> dict[str, Any]:
    """Expose persisted stock metrics and explicit unavailable rows for dashboard tabs."""
    metric_date = session.scalar(
        select(func.max(StockMetricDaily.metric_date)).where(
            StockMetricDaily.methodology_version == METHODOLOGY_VERSION
        )
    )
    if metric_date is None:
        return {"status": "unavailable", "data_date": None, "results": []}
    rows = session.scalars(
        select(StockMetricDaily)
        .where(
            StockMetricDaily.metric_date == metric_date,
            StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
        )
        .order_by(StockMetricDaily.symbol)
    ).all()

    def number(value: Any) -> float | None:
        return float(value) if value is not None else None

    return {
        "status": "available",
        "data_date": metric_date,
        "methodology_version": METHODOLOGY_VERSION,
        "results": [
            {
                "symbol": row.symbol,
                "quality_status": row.quality_status,
                "availability": "available" if row.score is not None else "unavailable",
                "score": number(row.score),
                "volatility_1m": number(row.volatility_1m),
                "volatility_3m": number(row.volatility_3m),
                "volatility_6m": number(row.volatility_6m),
                "volatility_1y": number(row.volatility_1y),
                "downside_volatility": number(row.downside_volatility),
                "max_drawdown": number(row.max_drawdown),
                "beta_nifty50": number(row.beta_nifty50),
                "average_traded_value_20d": number(row.average_traded_value_20d),
                "factors": {
                    "volatility": number(row.factor_volatility),
                    "downside": number(row.factor_downside),
                    "drawdown": number(row.factor_drawdown),
                    "beta": number(row.factor_beta),
                    "instability": number(row.factor_instability),
                },
                "observations_used": row.observations_used,
                "unavailable_reasons": row.missing_reasons,
            }
            for row in rows
        ],
    }
