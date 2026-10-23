"""Replaceable Yahoo Finance prototype adapter."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib.metadata import version
from threading import Lock
from time import monotonic, sleep
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yfinance as yf  # type: ignore[import-untyped]
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.app.market_data.types import DailyPrice

PROVIDER = "yfinance"
PROVIDER_VERSION = version("yfinance")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def normalize_history(frame: pd.DataFrame) -> list[DailyPrice]:
    """Convert a single-ticker yfinance history frame into typed daily observations."""
    if frame.empty:
        return []

    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required.difference(str(column) for column in frame.columns)
    if missing:
        raise ValueError(f"Yahoo response is missing columns: {sorted(missing)}")

    prices: list[DailyPrice] = []
    for timestamp, row in frame.iterrows():
        if pd.isna(row["Open"]) and pd.isna(row["Close"]):
            continue
        trade_date = pd.Timestamp(timestamp).date()
        adjusted = row.get("Adj Close", row["Close"])
        prices.append(
            DailyPrice(
                trade_date=trade_date,
                open=_decimal(row["Open"]),
                high=_decimal(row["High"]),
                low=_decimal(row["Low"]),
                close=_decimal(row["Close"]),
                adjusted_close=_decimal(adjusted),
                volume=-1 if pd.isna(row["Volume"]) else int(row["Volume"]),
                dividend=_decimal(row.get("Dividends", 0)),
                stock_split=_decimal(row.get("Stock Splits", 0)),
            )
        )
    return prices


class YahooFinanceClient:
    """Fetch daily research data without allowing provider details into the service layer."""

    provider = PROVIDER
    library_version = PROVIDER_VERSION

    def __init__(self, minimum_interval_seconds: float = 0.25) -> None:
        self.minimum_interval_seconds = max(minimum_interval_seconds, 0.0)
        self._rate_lock = Lock()
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        with self._rate_lock:
            remaining = self.minimum_interval_seconds - (monotonic() - self._last_request)
            if remaining > 0:
                sleep(remaining)
            self._last_request = monotonic()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(min=1, max=16),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def history(self, symbol: str, start: date, end: date) -> tuple[pd.DataFrame, list[DailyPrice]]:
        # Yahoo's end date is exclusive, so callers pass the desired final date plus one day.
        self._rate_limit()
        frame = yf.Ticker(symbol).history(
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=True,
            keepna=True,
            raise_errors=True,
            timeout=15,
        )
        return frame, normalize_history(frame)

    def verify(self, symbol: str, as_of: date) -> tuple[bool, str | None]:
        """Verify a provider ticker from observed daily data, including punctuation verbatim."""
        try:
            _, prices = self.history(symbol, as_of - timedelta(days=14), exclusive_end(as_of))
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"
        if not prices:
            return False, "provider_returned_no_daily_prices"
        return True, None

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=16), reraise=True)
    def fundamentals(self, symbol: str) -> tuple[date, dict[str, object], datetime]:
        """Return only fields actually supplied by Yahoo; absent fields are omitted."""
        self._rate_limit()
        ticker = yf.Ticker(symbol)
        info = ticker.get_info()
        fetched_at = datetime.now(UTC)
        reporting_epoch = info.get("mostRecentQuarter")
        as_of = (
            datetime.fromtimestamp(reporting_epoch, tz=UTC).date()
            if isinstance(reporting_epoch, (int, float))
            else fetched_at.date()
        )
        fields = {
            key: info[key]
            for key in (
                "marketCap",
                "trailingPE",
                "priceToBook",
                "enterpriseToEbitda",
                "debtToEquity",
                "returnOnEquity",
                "profitMargins",
                "dividendYield",
            )
            if info.get(key) is not None
        }
        return as_of, fields, fetched_at


def exclusive_end(inclusive_end: date) -> date:
    return inclusive_end + timedelta(days=1)
