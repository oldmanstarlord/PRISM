from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.market_data.live_service import (
    BenchmarkQuote,
    HistoricalBar,
    LiveQuote,
    MarketDataCache,
    fetch_benchmark,
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


@patch("backend.app.market_data.live_service.yf.Ticker")
def test_fetch_quote_live(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_fast = MagicMock()
    mock_fast.last_price = 3520.50
    mock_fast.previous_close = 3480.00
    mock_fast.open = 3490.00
    mock_fast.day_high = 3530.00
    mock_fast.day_low = 3475.00
    mock_fast.last_volume = 1200000
    mock_fast.currency = "INR"
    mock_ticker.fast_info = mock_fast
    mock_ticker.info = {
        "longName": "Tata Consultancy Services Limited",
        "sector": "Information Technology",
        "industry": "IT Services & Consulting",
    }
    mock_ticker_cls.return_value = mock_ticker

    quote = fetch_quote("TCS", force_refresh=True)
    assert quote.symbol == "TCS"
    assert quote.ticker == "TCS.NS"
    assert quote.currency == "INR"
    assert quote.latest_price == 3520.50
    assert quote.data_quality in {"live", "fallback"}
    assert quote.error is None


@patch("backend.app.market_data.live_service.yf.Ticker")
def test_fetch_quote_invalid_ticker_does_not_invent_zero(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_fast = MagicMock()
    mock_fast.last_price = None
    mock_fast.previous_close = None
    mock_ticker.fast_info = mock_fast
    mock_ticker_cls.return_value = mock_ticker

    quote = fetch_quote("NONEXISTENT_TICKER_9999", force_refresh=True)
    assert quote.symbol == "NONEXISTENT_TICKER_9999"
    # Never substitute missing prices with zero or fabricated values
    assert quote.latest_price is None
    assert quote.data_quality == "error"
    assert quote.error is not None
    assert "unavailable" in quote.error.lower() or "price unavailable" in quote.error.lower()


@patch("backend.app.market_data.live_service.yf.Ticker")
def test_fetch_benchmark(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_fast = MagicMock()
    mock_fast.last_price = 24500.00
    mock_fast.previous_close = 24400.00
    mock_ticker.fast_info = mock_fast
    mock_ticker_cls.return_value = mock_ticker

    bm = fetch_benchmark(force_refresh=True)
    assert bm.symbol == "^NSEI"
    assert bm.name == "NIFTY 50"
    assert bm.latest_price is not None
    assert bm.latest_price > 10000.0


@patch("backend.app.market_data.live_service.fetch_quote")
def test_api_quote_endpoint(mock_fetch):
    mock_fetch.return_value = LiveQuote(
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
    response = client.get("/api/v1/market-data/quote/TCS")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "TCS"
    assert data["currency"] == "INR"
    assert "latest_price" in data


@patch("backend.app.market_data.live_service.fetch_quote")
@patch("backend.app.market_data.live_service.fetch_benchmark")
def test_api_batch_quotes_endpoint(mock_bm, mock_fetch):
    mock_fetch.side_effect = lambda sym, **kwargs: LiveQuote(
        symbol=sym,
        ticker=f"{sym}.NS",
        company_name=sym,
        sector="Tech",
        industry="IT",
        latest_price=3000.0,
        previous_close=2950.0,
        change=50.0,
        change_percent=1.69,
        day_open=2960.0,
        day_high=3010.0,
        day_low=2955.0,
        volume=500000,
        currency="INR",
        as_of="2026-10-19T10:00:00Z",
        quote_type="live_quote",
        is_market_open=True,
        source="yfinance",
        data_quality="live",
        error=None,
    )
    mock_bm.return_value = BenchmarkQuote(
        symbol="^NSEI",
        name="NIFTY 50",
        latest_price=24500.0,
        previous_close=24400.0,
        change=100.0,
        change_percent=0.41,
        as_of="2026-10-19T10:00:00Z",
    )
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


@patch("backend.app.market_data.router.fetch_historical_ohlcv")
def test_api_historical_endpoint(mock_fetch_ohlcv):
    mock_fetch_ohlcv.return_value = [
        HistoricalBar(
            date="2026-10-01",
            open=3450.0,
            high=3480.0,
            low=3440.0,
            close=3470.0,
            adjusted_close=3470.0,
            volume=100000,
        ).to_dict(),
        HistoricalBar(
            date="2026-10-02",
            open=3460.0,
            high=3510.0,
            low=3455.0,
            close=3500.0,
            adjusted_close=3500.0,
            volume=150000,
        ).to_dict(),
    ]
    response = client.get("/api/v1/market-data/history/TCS?period=1mo")
    assert response.status_code == 200
    bars = response.json()
    assert isinstance(bars, list)
    assert len(bars) > 0
    assert "date" in bars[0]
    assert "close" in bars[0]
    assert "volume" in bars[0]
