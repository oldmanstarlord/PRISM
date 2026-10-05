"""Yahoo Finance ingestion adapter for macroeconomic and market series."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time
from typing import Any

from backend.app.macro.adapters.base import ParsedObservation

logger = logging.getLogger(__name__)

SERIES_YFINANCE_TICKERS: dict[str, str] = {
    "crude_oil": "BZ=F",
    "usd_inr": "INR=X",
    "in_10y_yield": "^IN10YT=RR",
    "india_vix": "^INDIAVIX",
}


class YahooMacroAdapter:
    """Fetches macroeconomic daily series from Yahoo Finance."""

    def __init__(self, yf_module: Any | None = None) -> None:
        if yf_module is None:
            try:
                import yfinance as yf

                self.yf = yf
            except ImportError:
                self.yf = None
        else:
            self.yf = yf_module

    @property
    def source_name(self) -> str:
        return "YAHOO"

    def fetch_observations(
        self,
        series_key: str,
        start_date: date | None = None,
        end_date: date | None = None,
        cutoff: datetime | None = None,
    ) -> list[ParsedObservation]:
        ticker = SERIES_YFINANCE_TICKERS.get(series_key)
        if not ticker or self.yf is None:
            return []

        start_str = start_date.isoformat() if start_date else "2020-01-01"
        end_str = end_date.isoformat() if end_date else date.today().isoformat()

        try:
            df = self.yf.download(
                ticker,
                start=start_str,
                end=end_str,
                progress=False,
                auto_adjust=False,
            )
        except Exception as exc:
            logger.warning("Yahoo finance fetch failed for %s (%s): %s", series_key, ticker, exc)
            return []

        if df is None or df.empty:
            return []

        observations: list[ParsedObservation] = []
        now = datetime.now(UTC)

        # Handle multi-level columns if returned by yfinance
        close_col = "Close"
        if isinstance(df.columns, type(df.columns)) and hasattr(df.columns, "levels"):
            try:
                df = df["Close"]
                if hasattr(df, "columns"):
                    close_series = df.iloc[:, 0]
                else:
                    close_series = df
            except Exception:
                close_series = df["Close"]
        else:
            close_series = df[close_col] if close_col in df else df.iloc[:, 0]

        for idx, val in close_series.items():
            if val is None:
                continue
            try:
                float_val = float(val)
                if float_val != float_val:  # NaN check
                    continue
            except (ValueError, TypeError):
                continue

            if hasattr(idx, "date"):
                obs_date = idx.date()
            else:
                obs_date = date.fromisoformat(str(idx)[:10])

            # Publication timestamp: 18:00 UTC on observation date
            published_at = datetime.combine(obs_date, time(18, 0), tzinfo=UTC)
            if cutoff and published_at > cutoff:
                continue

            observations.append(
                ParsedObservation(
                    series_key=series_key,
                    obs_date=obs_date,
                    value=float_val,
                    published_at=published_at,
                    ingested_at=now,
                    version=1,
                )
            )

        observations.sort(key=lambda o: o.obs_date)
        return observations
