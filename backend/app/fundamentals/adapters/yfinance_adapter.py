"""Yahoo Finance fundamentals adapter using official yfinance API (FR-D9)."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

from backend.app.fundamentals.adapters.base import ParsedDocument, ParsedPeriod, ResultAdapter

logger = logging.getLogger(__name__)


class YfinanceFundamentalsAdapter(ResultAdapter):
    """Fetches quarterly financial statements from Yahoo Finance API.

    Rules:
    - Source tag: YAHOO_FUNDAMENTALS
    - Yahoo does not provide regulatory publication dates. Published dates are
      strictly recorded as estimated: period_end + 45 days (or 60 days for annual).
    - Basis is recorded as 'unknown' (Yahoo does not reliably differentiate
      consolidated vs standalone in API data frames).
    """

    def __init__(
        self,
        quarterly_lag_days: int = 45,
        annual_lag_days: int = 60,
        request_delay: float = 0.5,
        max_retries: int = 3,
    ) -> None:
        self.quarterly_lag_days = quarterly_lag_days
        self.annual_lag_days = annual_lag_days
        self.request_delay = request_delay
        self.max_retries = max_retries

    @property
    def source_tag(self) -> str:
        return "YAHOO_FUNDAMENTALS"

    def _get_val(self, df: pd.DataFrame | None, col: Any, candidates: list[str]) -> float | None:
        if df is None or df.empty or col not in df.columns:
            return None
        for key in candidates:
            if key in df.index:
                val = df.loc[key, col]
                if pd.notna(val):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
        return None

    def fetch_results(
        self,
        symbol: str,
        isin: str | None = None,
        as_of: datetime | None = None,
    ) -> list[ParsedDocument]:
        ticker_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
        ingested_at = datetime.now(UTC)

        income_df: pd.DataFrame | None = None
        balance_df: pd.DataFrame | None = None
        cashflow_df: pd.DataFrame | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if self.request_delay > 0:
                    time.sleep(self.request_delay)
                ticker = yf.Ticker(ticker_sym)
                income_df = ticker.quarterly_income_stmt
                balance_df = ticker.quarterly_balance_sheet
                cashflow_df = ticker.quarterly_cashflow
                break
            except Exception as e:
                logger.warning(
                    "yfinance error on %s attempt %d/%d: %s",
                    ticker_sym,
                    attempt,
                    self.max_retries,
                    e,
                )
                if attempt == self.max_retries:
                    return []
                time.sleep(attempt * 1.0)

        # Collect distinct period dates
        period_dates: set[date] = set()
        for df in [income_df, balance_df, cashflow_df]:
            if df is not None and not df.empty:
                for col in df.columns:
                    if hasattr(col, "date"):
                        period_dates.add(col.date())
                    elif isinstance(col, (str, datetime)):
                        try:
                            period_dates.add(pd.to_datetime(col).date())
                        except Exception:
                            pass

        if not period_dates:
            return []

        periods: list[ParsedPeriod] = []
        for p_date in sorted(period_dates):
            # Yahoo provides ~4 to 5 trailing quarters
            estimated_published_at = datetime(
                p_date.year, p_date.month, p_date.day, 18, 0, tzinfo=UTC
            ) + timedelta(days=self.quarterly_lag_days)

            # Match column in DataFrames (could be Timestamp or date)
            def _find_matching_col(df: pd.DataFrame | None, target_date: date) -> Any:
                if df is None or df.empty:
                    return None
                for col in df.columns:
                    col_dt = getattr(col, "date", lambda: None)() or col
                    if col_dt == target_date:
                        return col
                return None

            col_inc = _find_matching_col(income_df, p_date)
            col_bal = _find_matching_col(balance_df, p_date)
            col_cf = _find_matching_col(cashflow_df, p_date)

            rev = self._get_val(
                income_df, col_inc, ["Total Revenue", "Operating Revenue", "Gross Profit"]
            )
            op_profit = self._get_val(
                income_df,
                col_inc,
                ["Operating Income", "EBIT", "Operating Revenue", "Pretax Income"],
            )
            pat = self._get_val(
                income_df,
                col_inc,
                [
                    "Net Income Common Stockholders",
                    "Net Income",
                    "Net Income Continuous Operations",
                ],
            )
            interest = self._get_val(
                income_df,
                col_inc,
                ["Interest Expense", "Interest Expense Non Operating", "Total Other Finance Cost"],
            )
            total_debt = self._get_val(
                balance_df,
                col_bal,
                [
                    "Total Debt",
                    "Long Term Debt",
                    "Current Debt",
                    "Long Term Debt And Capital Lease Obligation",
                ],
            )
            total_equity = self._get_val(
                balance_df,
                col_bal,
                ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"],
            )
            total_assets = self._get_val(balance_df, col_bal, ["Total Assets"])
            cfo = self._get_val(
                cashflow_df,
                col_cf,
                ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
            )

            # Bank/financial items mapping if present
            extra: dict[str, Any] = {}
            nii = self._get_val(income_df, col_inc, ["Net Interest Income"])
            if nii is not None:
                extra["net_interest_income"] = nii

            period = ParsedPeriod(
                period_end=p_date,
                period_type="quarter",
                basis="unknown",
                published_at=estimated_published_at,
                published_at_method="estimated",
                revenue=rev,
                operating_profit=op_profit,
                pat=pat,
                interest_expense=interest,
                total_debt=total_debt,
                total_equity=total_equity,
                total_assets=total_assets,
                cash_from_operations=cfo,
                extra=extra,
            )
            periods.append(period)

        if not periods:
            return []

        doc_hash = hashlib.sha256(
            f"{symbol}:{ticker_sym}:{len(periods)}:{ingested_at.isoformat()}".encode()
        ).hexdigest()

        doc = ParsedDocument(
            source=self.source_tag,
            doc_type="quarterly_results",
            published_at=max(p.published_at for p in periods),
            published_at_method="estimated",
            content_hash=doc_hash,
            source_doc_id=f"yfinance_{symbol}_{periods[-1].period_end.isoformat()}",
            url=f"https://finance.yahoo.com/quote/{ticker_sym}/financials",
            raw_path=None,
            periods=periods,
        )
        return [doc]
