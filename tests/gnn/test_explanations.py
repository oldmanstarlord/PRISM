from datetime import date, timedelta

import numpy as np
import pandas as pd

from backend.app.gnn.explanations import explain


def test_peer_exclusion_and_missing_snapshot_breaks_streak():
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(45)]
    prices = pd.DataFrame(
        {
            name: np.linspace(100, end, 45)
            for name, end in [("A", 160), ("B", 110), ("C", 110), ("D", 110)]
        },
        index=days,
    )
    rows = [
        {
            "date": day,
            "symbol": symbol,
            "industry": "IT",
            "alert_level": "elevated",
            "drift_percentile": 0.97,
        }
        for day in days[-3:]
        for symbol in prices
        if not (symbol == "A" and day == days[-2])
    ]
    result = explain(["A", "B"], rows, prices)
    a = result["stocks"]["A"]
    assert a["peer_comparison"]["symbols"] == ["B", "C", "D"]
    assert a["peer_comparison"]["gap"] > 0
    assert a["persistence"]["consecutive_elevated"] == 1
    assert a["persistence"]["missing_snapshots"] == 1
    assert result["diversification"]["pairs"] == 1


def test_insufficient_data_is_unavailable_not_zero():
    result = explain(
        ["A"],
        [
            {
                "date": date(2026, 1, 1),
                "symbol": "A",
                "industry": "IT",
                "alert_level": "normal",
                "drift_percentile": 0.5,
            }
        ],
        pd.DataFrame(),
    )
    assert result["diversification"]["status"] == "unavailable"
    assert result["stocks"]["A"]["peer_comparison"]["status"] == "unavailable"


def test_future_prices_do_not_change_explanation():
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(50)]
    prices = pd.DataFrame({"A": np.arange(50) + 100}, index=days)
    rows = [
        {
            "date": days[44],
            "symbol": "A",
            "industry": "IT",
            "alert_level": "normal",
            "drift_percentile": 0.5,
        }
    ]
    assert explain(["A"], rows, prices) == explain(["A"], rows, prices.iloc[:45])
