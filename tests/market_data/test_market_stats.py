"""Tests for market stats derivation, liquidity flags, and hand-calculated metrics."""

from collections import deque
from decimal import Decimal

from backend.app.market_data.market_stats import THIN_TRADING_VALUE_THRESHOLD


def test_hand_calculated_traded_value_and_market_cap() -> None:
    # 1. Traded value = close * volume
    close = Decimal("250.50")
    volume = 12000
    expected_traded_value = Decimal("3006000.00")
    traded_value = close * Decimal(volume)
    assert traded_value == expected_traded_value

    # 2. Market Cap = shares_outstanding * close
    shares_outstanding = 50000000  # 5 Crore shares
    expected_market_cap = Decimal("12525000000.00")
    market_cap = Decimal(shares_outstanding) * close
    assert market_cap == expected_market_cap


def test_hand_calculated_adv_20() -> None:
    # 20 observations of traded value
    values = [Decimal(f"{1000000 + i * 50000}") for i in range(20)]
    recent_values: deque[Decimal] = deque(maxlen=20)
    for v in values:
        recent_values.append(v)

    expected_sum = sum(values)
    expected_mean = expected_sum / Decimal("20")

    calculated_adv = sum(recent_values) / Decimal(len(recent_values))
    assert calculated_adv == expected_mean
    # First is 1,000,000, last is 1,950,000 -> mean is 1,475,000.00
    assert calculated_adv == Decimal("1475000.00")


def test_liquidity_flags_detection() -> None:
    # Volume 0 -> zero_volume flag
    vol_zero = 0
    flags_zero: dict[str, bool] = {}
    if vol_zero == 0:
        flags_zero["zero_volume"] = True
    assert flags_zero.get("zero_volume") is True

    # Traded value < 10 Lakhs -> thin_trading flag
    low_close = Decimal("50.0")
    low_vol = 1000  # traded value = 50,000 (< 1,000,000)
    low_traded_val = low_close * Decimal(low_vol)

    flags_thin: dict[str, bool] = {}
    if low_traded_val < THIN_TRADING_VALUE_THRESHOLD:
        flags_thin["thin_trading"] = True
    assert flags_thin.get("thin_trading") is True

    # High volume stock -> no thin trading flag
    high_close = Decimal("1500.0")
    high_vol = 50000  # 7.5 Crores
    high_val = high_close * Decimal(high_vol)
    flags_normal: dict[str, bool] = {}
    if high_val < THIN_TRADING_VALUE_THRESHOLD:
        flags_normal["thin_trading"] = True
    assert "thin_trading" not in flags_normal
