"""Tests for live market data service and yfinance integration."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.market_data.live_service import (
    LiveQuote,
    MarketDataCache,
    fetch_batch_quotes,
    fetch_benchmark,
    fetch_historical_ohlcv,
    fetch_quote,
    normalize_symbol_for_yahoo,
)

client = TestClient(app)


def test_normalize_symbol_for_yahoo():
    assert normalize_symbol_for_yahoo("tcs") == ("TCS", "TCS.NS")
    assert normalize_symbol_for_yahoo("INFY.NS") == ("INFY", "INFY.NS")
    assert normalize_symbol_for_yahoo("^NSEI") == ("^NSEI", "^NSEI")
    assert normalize_symbol_for_yahoo("RELIANCE.BO") == ("RELIANCE", "RELIANCE.BO")


def test_market_data_cache():
    cache = MarketDataCache()
    sample_quote = LiveQuote(
        symbol="TCS",
        ticker="TCS.NS",
        company_name="Tata Consultancy Services",
        sector="Technology",
        industry="IT Services",
        latest_price=3500.0,
        previous_close=3450.0,
        change=50.0,
        change_percent=1.45,
        day_open=3460.0,
        day_high=3510.0,
        day_low=3455.0,
        volume=1000000,
        currency="INR",
        as_of="2026-10-19T10:00:00Z",
        quote_type="live_quote",
        is_market_open=True,
        source="yfinance",
        data_quality="live",
        error=None,
    )
    assert cache.get_quote("TCS") is None
    cache.set_quote("TCS", sample_quote)
    cached = cache.get_quote("tcs")
    assert cached is not None
    assert cached.latest_price == 3500.0
    assert cached.symbol == "TCS"


def test_fetch_quote_live():
    # Fetch real live quote for TCS
    quote = fetch_quote("TCS")
    assert quote.symbol == "TCS"
    assert quote.ticker == "TCS.NS"
    assert quote.currency == "INR"
    if quote.latest_price is not None:
        assert quote.latest_price > 0
        assert quote.data_quality in {"live", "fallback"}
        assert quote.error is None


def test_fetch_quote_invalid_ticker_does_not_invent_zero():
    quote = fetch_quote("NONEXISTENT_TICKER_9999")
    assert quote.symbol == "NONEXISTENT_TICKER_9999"
    # Never substitute missing prices with zero or fabricated values
    assert quote.latest_price is None
    assert quote.data_quality == "error"
    assert quote.error is not None
    assert "unavailable" in quote.error.lower() or "price unavailable" in quote.error.lower()


def test_fetch_benchmark():
    bm = fetch_benchmark()
    assert bm.symbol == "^NSEI"
    assert bm.name == "NIFTY 50"
    if bm.latest_price is not None:
        assert bm.latest_price > 10000.0


def test_api_quote_endpoint():
    response = client.get("/api/v1/market-data/quote/TCS")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "TCS"
    assert data["currency"] == "INR"
    assert "latest_price" in data


def test_api_batch_quotes_endpoint():
    response = client.post(
        "/api/v1/market-data/quotes",
        json={"symbols": ["TCS", "INFY"], "force_refresh": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert "quotes" in data
    assert "benchmark" in data
    assert "TCS" in data["quotes"]
    assert "INFY" in data["quotes"]


def test_api_historical_endpoint():
    response = client.get("/api/v1/market-data/history/TCS?period=1mo")
    assert response.status_code == 200
    bars = response.json()
    assert isinstance(bars, list)
    if len(bars) > 0:
        assert "date" in bars[0]
        assert "close" in bars[0]
        assert "volume" in bars[0]
