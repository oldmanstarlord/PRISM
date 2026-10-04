from datetime import date
from decimal import Decimal

import pandas as pd

from backend.app.market_data.yahoo import exclusive_end, normalize_history


def test_normalize_history_preserves_prices_and_actions() -> None:
    frame = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [105.0],
            "Low": [99.0],
            "Close": [104.0],
            "Adj Close": [103.5],
            "Volume": [1234],
            "Dividends": [2.5],
            "Stock Splits": [0.0],
        },
        index=pd.DatetimeIndex(["2026-01-05"], name="Date"),
    )

    result = normalize_history(frame)

    assert len(result) == 1
    assert result[0].trade_date == date(2026, 1, 5)
    assert result[0].adjusted_close == Decimal("103.5")
    assert result[0].dividend == Decimal("2.5")
    assert result[0].volume == 1234


def test_exclusive_end_adds_one_day() -> None:
    assert exclusive_end(date(2026, 1, 31)) == date(2026, 2, 1)
