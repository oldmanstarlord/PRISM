"""FastAPI router exposing market data and live quotes powered by yfinance."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.session import get_session
from backend.app.market_data.live_service import (
    fetch_batch_quotes,
    fetch_benchmark,
    fetch_historical_ohlcv,
    fetch_quote,
)

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
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    """Retrieve current level and day change for the NIFTY 50 benchmark."""
    benchmark = fetch_benchmark(force_refresh=force_refresh)
    return benchmark.to_dict()


@router.get("/history/{symbol}")
def get_history(
    symbol: str,
    period: str = Query(default="1mo", pattern="^(5d|1mo|3mo|6mo|1y|2y|5y|max)$"),
    interval: str = Query(default="1d", pattern="^(1d|1wk|1mo)$"),
    force_refresh: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """Retrieve historical daily OHLCV bars for charts and risk models."""
    return fetch_historical_ohlcv(
        symbol,
        period=period,
        interval=interval,
        force_refresh=force_refresh,
    )
