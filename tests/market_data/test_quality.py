from datetime import date
from decimal import Decimal

from backend.app.market_data.quality import validate_prices
from backend.app.market_data.types import DailyPrice


def price(
    day: int,
    *,
    open_price: str = "100",
    high: str = "105",
    low: str = "95",
    close: str = "102",
    adjusted_close: str = "102",
    volume: int = 1_000,
) -> DailyPrice:
    return DailyPrice(
        trade_date=date(2026, 1, day),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        adjusted_close=Decimal(adjusted_close),
        volume=volume,
    )


def test_valid_prices_are_accepted_in_date_order() -> None:
    result = validate_prices([price(6), price(5)])

    assert [item.trade_date.day for item in result.accepted] == [5, 6]
    assert result.rejected_rows == 0


def test_invalid_ohlc_and_negative_volume_are_rejected() -> None:
    result = validate_prices([price(5, high="99", volume=-1)])

    assert result.accepted == ()
    assert result.rejected_rows == 1
    assert {issue.code for issue in result.issues} == {"invalid_high", "negative_volume"}


def test_duplicate_date_is_rejected() -> None:
    result = validate_prices([price(5), price(5)])

    assert len(result.accepted) == 1
    assert result.rejected_rows == 1
    assert result.issues[0].code == "duplicate_date"


def test_extreme_return_and_long_gap_are_flagged() -> None:
    result = validate_prices(
        [price(5, adjusted_close="100"), price(20, adjusted_close="150", close="150", high="155")]
    )

    flags = result.accepted[-1].quality_flags
    assert "extreme_adjusted_return" in flags
    assert "long_observation_gap" in flags
    assert result.warning_count == 2
