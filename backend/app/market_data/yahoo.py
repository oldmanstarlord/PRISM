"""Replaceable Yahoo Finance prototype adapter."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.app.market_data.types import DailyPrice


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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
    def history(self, symbol: str, start: date, end: date) -> tuple[pd.DataFrame, list[DailyPrice]]:
        # Yahoo's end date is exclusive, so callers pass the desired final date plus one day.
        frame = yf.Ticker(symbol).history(
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=True,
            keepna=True,
            raise_errors=True,
        )
        return frame, normalize_history(frame)


def exclusive_end(inclusive_end: date) -> date:
    return inclusive_end + timedelta(days=1)
