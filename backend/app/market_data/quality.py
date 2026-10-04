"""Deterministic quality rules for daily price observations."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from backend.app.market_data.types import DailyPrice, QualityIssue, QualityResult

EXTREME_DAILY_RETURN = Decimal("0.40")


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
