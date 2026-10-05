"""Hand-calculated numeric tests for Step 8 governance metrics.

Requirements:
- Hand-calculated pledge change
- Hand-calculated institutional flow
- Hand-calculated net insider selling value and ratio to market cap
- Determinism (same inputs => same outputs)
- Missing-data handling
"""

from datetime import date

from backend.app.governance.config import GovernanceAnalysisConfig
from backend.app.governance.metrics import (
    compute_insider_activity,
    compute_institutional_flow,
    compute_pledge_metrics,
)


def test_hand_calculated_pledge_metrics() -> None:
    """Hand-calculated verification of pledge level and 2-quarter change."""
    # Pattern rows: sorted newest-first
    # Q3 (latest): 2025-12-31, pledge = 25.0%
    # Q2:          2025-09-30, pledge = 18.0%
    # Q1 (base):   2025-06-30, pledge = 10.0%
    patterns = [
        {
            "quarter_end": date(2025, 12, 31),
            "promoter_pct": 60.0,
            "promoter_pledged_pct_of_promoter": 25.0,
        },
        {
            "quarter_end": date(2025, 9, 30),
            "promoter_pct": 60.0,
            "promoter_pledged_pct_of_promoter": 18.0,
        },
        {
            "quarter_end": date(2025, 6, 30),
            "promoter_pct": 60.0,
            "promoter_pledged_pct_of_promoter": 10.0,
        },
    ]

    config = GovernanceAnalysisConfig(min_quarters_for_change=2)
    metrics = compute_pledge_metrics(patterns, config=config)

    # Hand-calc:
    # Latest pledge_level = 25.0%
    # Prior quarter (sorted_pats[-2]) = 18.0%
    # Change = 25.0 - 18.0 = +7.0%
    assert metrics.pledge_level == 25.0
    assert metrics.pledge_change == 7.0
    assert metrics.promoter_pct == 60.0
    assert metrics.promoter_change == 0.0
    assert metrics.n_quarters_available == 3
    assert metrics.status == "ok"


def test_pledge_metrics_incomplete_history() -> None:
    """When fewer than lookback_quarters are available, change is None."""
    patterns = [
        {
            "quarter_end": date(2025, 12, 31),
            "promoter_pct": 55.0,
            "promoter_pledged_pct_of_promoter": 5.0,
        }
    ]

    config = GovernanceAnalysisConfig(min_quarters_for_change=2)
    metrics = compute_pledge_metrics(patterns, config=config)

    assert metrics.pledge_level == 5.0
    assert metrics.pledge_change is None
    assert metrics.promoter_pct == 55.0
    assert metrics.promoter_change is None
    assert metrics.n_quarters_available == 1
    assert metrics.status == "ok"


def test_pledge_metrics_empty_data() -> None:
    """Empty shareholding pattern returns status='missing'."""
    config = GovernanceAnalysisConfig()
    metrics = compute_pledge_metrics([], config=config)

    assert metrics.pledge_level is None
    assert metrics.pledge_change is None
    assert metrics.status == "missing"
    assert metrics.n_quarters_available == 0


def test_hand_calculated_institutional_flow() -> None:
    """Hand-calculated verification of FII + DII holding change over 2 quarters."""
    patterns = [
        {"quarter_end": date(2025, 12, 31), "fii_pct": 20.0, "dii_pct": 15.0},
        {"quarter_end": date(2025, 9, 30), "fii_pct": 19.0, "dii_pct": 14.0},
        {"quarter_end": date(2025, 6, 30), "fii_pct": 18.0, "dii_pct": 13.0},
    ]

    config = GovernanceAnalysisConfig(institutional_flow_lookback_quarters=2)
    metrics = compute_institutional_flow(patterns, config=config)

    # Hand-calc:
    # Combined latest = 20.0 + 15.0 = 35.0%
    # Prior quarter = 19.0 + 14.0 = 33.0%
    # Net institutional change = 35.0 - 33.0 = +2.0%
    assert metrics.combined_pct == 35.0
    assert metrics.fii_pct == 20.0
    assert metrics.dii_pct == 15.0
    assert metrics.institutional_change == 2.0
    assert metrics.n_quarters_available == 3
    assert metrics.status == "ok"


def test_hand_calculated_insider_activity() -> None:
    """Hand-calculated verification of insider buy/sell value, net value, and market cap ratio."""
    as_of = date(2026, 1, 15)
    config = GovernanceAnalysisConfig(insider_window_days=180)

    trades = [
        {"txn_date": date(2025, 11, 1), "txn_type": "sell", "value": 40_000_000.0},
        {"txn_date": date(2025, 10, 15), "txn_type": "buy", "value": 10_000_000.0},
        {"txn_date": date(2025, 8, 1), "txn_type": "sell", "value": 20_000_000.0},
        {"txn_date": date(2025, 1, 1), "txn_type": "sell", "value": 99_000_000.0},
    ]

    market_cap_inr = 10_000_000_000.0  # 1,000 Cr INR

    metrics = compute_insider_activity(
        trades=trades,
        as_of=as_of,
        config=config,
        market_cap_inr=market_cap_inr,
    )

    assert metrics.trade_count == 3
    assert metrics.sell_value == 60_000_000.0
    assert metrics.buy_value == 10_000_000.0
    assert metrics.net_sell_value == 50_000_000.0
    assert metrics.insider_sell_ratio is not None
    assert abs(metrics.insider_sell_ratio - 0.005) < 1e-9
    assert metrics.status == "ok"


def test_insider_activity_zero_trades() -> None:
    """When no trades occurred in window, status is missing and ratio is None."""
    as_of = date(2026, 1, 15)
    config = GovernanceAnalysisConfig()

    metrics = compute_insider_activity(
        trades=[],
        as_of=as_of,
        config=config,
        market_cap_inr=5_000_000_000.0,
    )

    assert metrics.trade_count == 0
    assert metrics.buy_value == 0.0
    assert metrics.sell_value == 0.0
    assert metrics.net_sell_value == 0.0
    assert metrics.insider_sell_ratio is None
    assert metrics.status == "missing"


def test_governance_metrics_determinism() -> None:
    """Deterministic calculation: identical inputs yield identical outputs (D6)."""
    patterns = [
        {
            "quarter_end": date(2025, 12, 31),
            "promoter_pct": 50.0,
            "promoter_pledged_pct_of_promoter": 12.0,
        },
        {
            "quarter_end": date(2025, 9, 30),
            "promoter_pct": 50.0,
            "promoter_pledged_pct_of_promoter": 10.0,
        },
    ]

    config = GovernanceAnalysisConfig(min_quarters_for_change=1)
    m1 = compute_pledge_metrics(patterns, config=config)
    m2 = compute_pledge_metrics(patterns, config=config)

    assert m1.pledge_level == m2.pledge_level
    assert m1.pledge_change == m2.pledge_change
    assert m1.status == m2.status
