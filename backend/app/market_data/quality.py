"""Deterministic row and symbol-level quality rules for daily market data."""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from backend.app.market_data.types import DailyPrice, QualityIssue, QualityResult

EXTREME_DAILY_RETURN = Decimal("0.40")
MIN_HISTORY_SESSIONS = 252
ZERO_VOLUME_STREAK = 5


@dataclass(frozen=True, slots=True)
class SymbolQuality:
    status: str
    reasons: tuple[str, ...]
    observations: int
    expected_sessions: int | None
    last_trade_date: date | None


def evaluate_symbol_quality(
    prices: list[DailyPrice],
    *,
    expected_sessions: set[date] | None,
    corporate_action_dates: set[date],
    as_of: date,
) -> SymbolQuality:
    """Evaluate a complete series without inventing exchange sessions or observations."""
    ordered = sorted(prices, key=lambda item: item.trade_date)
    if not ordered:
        return SymbolQuality("fail", ("missing_price_history",), 0, None, None)

    failures: set[str] = set()
    warnings: set[str] = set()
    if len(ordered) < MIN_HISTORY_SESSIONS:
        warnings.add("insufficient_history")
    if any(min(p.open, p.high, p.low, p.close, p.adjusted_close) <= 0 for p in ordered):
        failures.add("non_positive_price")

    for prior, current in zip(ordered, ordered[1:], strict=False):
        move = abs(current.adjusted_close / prior.adjusted_close - 1)
        if move > EXTREME_DAILY_RETURN and current.trade_date not in corporate_action_dates:
            warnings.add("move_over_40pct_without_corporate_action")
    max_streak = current_streak = 0
    for item in ordered:
        current_streak = current_streak + 1 if item.volume == 0 else 0
        max_streak = max(max_streak, current_streak)
    if max_streak >= ZERO_VOLUME_STREAK:
        warnings.add("zero_volume_streak")

    expected_count: int | None = None
    if expected_sessions is None:
        warnings.add("trading_calendar_unavailable")
    else:
        first = ordered[0].trade_date
        relevant = {day for day in expected_sessions if first <= day <= as_of}
        expected_count = len(relevant)
        missing = relevant.difference(item.trade_date for item in ordered)
        if missing:
            warnings.add("missing_trading_sessions")
        if expected_count and len(missing) / expected_count > 0.05:
            failures.add("excessive_trading_session_gaps")
        last_expected = max((day for day in expected_sessions if day <= as_of), default=None)
        if last_expected is not None and ordered[-1].trade_date < last_expected:
            warnings.add("stale_last_date")

    reasons = tuple(sorted(failures or warnings))
    status = "fail" if failures else "warn" if warnings else "pass"
    return SymbolQuality(status, reasons, len(ordered), expected_count, ordered[-1].trade_date)


def validate_prices(prices: list[DailyPrice]) -> QualityResult:
    issues: list[QualityIssue] = []
    accepted: list[DailyPrice] = []
    seen_dates: set[object] = set()
    previous: DailyPrice | None = None
    rejected = 0

    for price in sorted(prices, key=lambda item: item.trade_date):
        rejection_reasons: list[str] = []
        if price.trade_date in seen_dates:
            rejection_reasons.append("duplicate_date")
        seen_dates.add(price.trade_date)
        values = (price.open, price.high, price.low, price.close, price.adjusted_close)
        if not all(value.is_finite() for value in values):
            rejection_reasons.append("missing_or_non_finite_price")
        elif min(values) <= 0:
            rejection_reasons.append("non_positive_price")
        if all(value.is_finite() for value in values) and price.high < max(
            price.open, price.low, price.close
        ):
            rejection_reasons.append("invalid_high")
        if all(value.is_finite() for value in values) and price.low > min(
            price.open, price.high, price.close
        ):
            rejection_reasons.append("invalid_low")
        if price.volume < 0:
            rejection_reasons.append("negative_volume")

        if rejection_reasons:
            rejected += 1
            issues.extend(
                QualityIssue(code, "error", f"Rejected row: {code}", price.trade_date)
                for code in rejection_reasons
            )
            continue

        flags: list[str] = []
        if previous is not None:
            gap = price.trade_date - previous.trade_date
            if gap > timedelta(days=7):
                flags.append("long_observation_gap")
                issues.append(
                    QualityIssue(
                        "long_observation_gap",
                        "warning",
                        f"{gap.days}-day gap since prior observation",
                        price.trade_date,
                    )
                )
            daily_return = abs(price.adjusted_close / previous.adjusted_close - 1)
            if daily_return > EXTREME_DAILY_RETURN:
                flags.append("extreme_adjusted_return")
                issues.append(
                    QualityIssue(
                        "extreme_adjusted_return",
                        "warning",
                        f"Absolute adjusted return is {daily_return:.2%}",
                        price.trade_date,
                    )
                )
        accepted_price = replace(price, quality_flags=tuple(flags))
        accepted.append(accepted_price)
        previous = accepted_price

    return QualityResult(tuple(accepted), rejected, tuple(issues))
