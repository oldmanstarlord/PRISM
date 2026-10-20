"""Comprehensive tests for Phase 2: Portfolio Ledger Integrity and Accounting Engine.

Tests:
- Weighted-Average Cost (WAC) basis calculations.
- Buy, partial sell, dividend, fee, deposit, and withdrawal lifecycle.
- Realized and unrealized P&L separation.
- Rejection of over-selling (sell quantity > held quantity).
- Rejection of negative amounts, prices, quantities, and fees.
- Rejection of future transaction dates.
- Cash overdraft prevention on withdrawals.
- Formula injection detection and sanitization for spreadsheet security.
- CSV parsing, column mapping, row-level validation, and atomic validation.
- CSV export sanitization.
- Reconciliation report generation between ledger-derived state and external displays.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.portfolio.ledger import (
    DerivedHolding,
    FormulaInjectionError,
    LedgerState,
    LedgerTransactionInput,
    LedgerValidationError,
    check_formula_injection,
    export_csv_transactions,
    parse_csv_transactions,
    reconcile_ledger,
    replay_ledger,
    validate_transaction_input,
)


def test_formula_injection_defense() -> None:
    """Ensure spreadsheet formulas starting with =, +, -, @, \\t, \\r are rejected."""
    malicious_inputs = [
        "=SUM(A1:A10)",
        "+cmd|' /C calc'!A0",
        "-12345",
        "@SUM(B1)",
        "\tmalicious",
        "\rtest",
    ]
    for bad in malicious_inputs:
        with pytest.raises(FormulaInjectionError):
            check_formula_injection(bad)

    # Safe inputs must pass
    safe_inputs = ["TCS", "INFY", "Initial portfolio deposit", "Regular buy order"]
    for safe in safe_inputs:
        check_formula_injection(safe)


def test_validate_transaction_input_rejects_invalid_values() -> None:
    """Ensure negative amounts, unknown types, and future dates are rejected."""
    today = date.today()
    future = today + timedelta(days=2)

    # Future date
    with pytest.raises(LedgerValidationError, match="in the future"):
        validate_transaction_input(
            LedgerTransactionInput(
                id="tx-future",
                transaction_type="BUY",
                trade_date=future,
                symbol="TCS",
                quantity=Decimal("10"),
                price=Decimal("3500"),
            ),
            as_of=today,
        )

    # Negative fee
    with pytest.raises(LedgerValidationError, match="Fees cannot be negative"):
        validate_transaction_input(
            LedgerTransactionInput(
                id="tx-fee",
                transaction_type="BUY",
                trade_date=today,
                symbol="TCS",
                quantity=Decimal("10"),
                price=Decimal("3500"),
                fees=Decimal("-5.0"),
            )
        )

    # Negative quantity
    with pytest.raises(LedgerValidationError, match="Quantity must be strictly positive"):
        validate_transaction_input(
            LedgerTransactionInput(
                id="tx-qty",
                transaction_type="BUY",
                trade_date=today,
                symbol="TCS",
                quantity=Decimal("-10"),
                price=Decimal("3500"),
            )
        )

    # Negative price
    with pytest.raises(LedgerValidationError, match="Price must be strictly positive"):
        validate_transaction_input(
            LedgerTransactionInput(
                id="tx-px",
                transaction_type="BUY",
                trade_date=today,
                symbol="TCS",
                quantity=Decimal("10"),
                price=Decimal("-100"),
            )
        )

    # Missing symbol on BUY
    with pytest.raises(LedgerValidationError, match="Symbol is required"):
        validate_transaction_input(
            LedgerTransactionInput(
                id="tx-sym",
                transaction_type="BUY",
                trade_date=today,
                symbol="",
                quantity=Decimal("10"),
                price=Decimal("100"),
            )
        )

    # Negative deposit amount
    with pytest.raises(LedgerValidationError, match="Amount must be strictly positive"):
        validate_transaction_input(
            LedgerTransactionInput(
                id="tx-dep",
                transaction_type="DEPOSIT",
                trade_date=today,
                amount=Decimal("-50000"),
            )
        )


def test_wac_lifecycle_buy_sell_dividend_deposit() -> None:
    """Replay standard lifecycle and verify exact WAC accounting formulas.

    Lifecycle:
    1. Deposit ₹10,00,000 cash.
    2. Buy 100 shares TCS @ ₹3,000 + ₹100 fee.
       Invested cost = ₹3,00,100. Unit avg cost = ₹3,001.00.
    4. Buy 100 shares TCS @ ₹3,200 + ₹100 fee.
       Total shares = 200. Total outlay = ₹3,20,100.
       Total invested cost = ₹3,00,100 + ₹3,20,100 = ₹6,20,200.
       Unit avg cost = ₹6,20,200 / 200 = ₹3,101.00.
    5. Partial sell 50 shares TCS @ ₹3,500 with ₹50 fee.
       Cost basis sold = 50 * ₹3,101.00 = ₹1,55,050.
       Gross proceeds = 50 * ₹3,500 = ₹1,75,000.
       Net proceeds = ₹1,75,000 - ₹50 = ₹1,74,950.
       Realized P&L = Net proceeds - Cost basis sold = ₹1,74,950 - ₹1,55,050 = ₹19,900.
       Remaining shares = 150.
       Remaining invested cost = 150 * ₹3,101.00 = ₹4,65,150.
    6. Dividend of ₹2,500 on TCS. Cash increases by ₹2,500; invested cost of shares unchanged.
    7. Withdrawal of ₹50,000 cash.
    """
    d1 = date(2026, 1, 5)
    d2 = date(2026, 1, 10)
    d3 = date(2026, 1, 15)
    d4 = date(2026, 1, 20)
    d5 = date(2026, 1, 25)
    d6 = date(2026, 2, 1)

    txs = [
        LedgerTransactionInput(
            id="tx-1",
            transaction_type="DEPOSIT",
            trade_date=d1,
            amount=Decimal("1000000.00"),
            notes="Initial capital funding",
        ),
        LedgerTransactionInput(
            id="tx-2",
            transaction_type="BUY",
            trade_date=d2,
            symbol="TCS",
            quantity=Decimal("100"),
            price=Decimal("3000.00"),
            fees=Decimal("100.00"),
        ),
        LedgerTransactionInput(
            id="tx-3",
            transaction_type="BUY",
            trade_date=d3,
            symbol="TCS",
            quantity=Decimal("100"),
            price=Decimal("3200.00"),
            fees=Decimal("100.00"),
        ),
        LedgerTransactionInput(
            id="tx-4",
            transaction_type="SELL",
            trade_date=d4,
            symbol="TCS",
            quantity=Decimal("50"),
            price=Decimal("3500.00"),
            fees=Decimal("50.00"),
        ),
        LedgerTransactionInput(
            id="tx-5",
            transaction_type="DIVIDEND",
            trade_date=d5,
            symbol="TCS",
            amount=Decimal("2500.00"),
            notes="TCS interim dividend",
        ),
        LedgerTransactionInput(
            id="tx-6",
            transaction_type="WITHDRAWAL",
            trade_date=d6,
            amount=Decimal("50000.00"),
            notes="Owner capital withdrawal",
        ),
    ]

    state = replay_ledger(
        txs,
        market_prices={"TCS": Decimal("3600.00")},
        as_of=date(2026, 2, 15),
    )

    # Validate remaining shares & invested cost
    tcs = state.holdings["TCS"]
    assert tcs.quantity == Decimal("150")
    assert tcs.average_cost == Decimal("3101.00")
    assert tcs.invested_cost == Decimal("465150.00")
    assert tcs.market_price == Decimal("3600.00")
    assert tcs.market_value == Decimal("540000.00")  # 150 * 3600

    # Unrealized P&L = 540,000 - 465,150 = 74,850
    assert tcs.unrealized_pnl == Decimal("74850.00")
    # Realized P&L = 19,900
    assert tcs.realized_pnl == Decimal("19900.00")
    assert state.realized_pnl == Decimal("19900.00")

    # Cash calculation:
    # + 1,000,000 (deposit)
    # - 300,100 (buy 1)
    # - 320,100 (buy 2)
    # + 174,950 (sell proceeds)
    # + 2,500 (dividend)
    # - 50,000 (withdrawal)
    # = 507,250
    assert state.cash == Decimal("507250.00")
    assert state.total_dividends == Decimal("2500.00")
    assert state.total_fees == Decimal("250.00")  # 100 + 100 + 50
    assert state.net_deposits == Decimal("950000.00")  # 1,000,000 - 50,000

    # Portfolio total market value = cash + holdings market value = 507,250 + 540,000 = 1,047,250
    assert state.total_portfolio_value() == Decimal("1047250.00")


def test_rejection_of_overselling() -> None:
    """Attempting to sell more shares than currently held must raise LedgerValidationError."""
    txs = [
        LedgerTransactionInput(
            id="tx-1",
            transaction_type="DEPOSIT",
            trade_date=date(2026, 1, 1),
            amount=Decimal("100000"),
        ),
        LedgerTransactionInput(
            id="tx-2",
            transaction_type="BUY",
            trade_date=date(2026, 1, 5),
            symbol="INFY",
            quantity=Decimal("20"),
            price=Decimal("1500"),
        ),
        LedgerTransactionInput(
            id="tx-3",
            transaction_type="SELL",
            trade_date=date(2026, 1, 10),
            symbol="INFY",
            quantity=Decimal("25"),  # Holds only 20
            price=Decimal("1600"),
        ),
    ]

    with pytest.raises(LedgerValidationError, match="Cannot sell 25 shares of INFY; only 20"):
        replay_ledger(txs)


def test_rejection_of_cash_overdraft() -> None:
    """Attempting to withdraw more cash than available must raise LedgerValidationError."""
    txs = [
        LedgerTransactionInput(
            id="tx-1",
            transaction_type="DEPOSIT",
            trade_date=date(2026, 1, 1),
            amount=Decimal("10000"),
        ),
        LedgerTransactionInput(
            id="tx-2",
            transaction_type="WITHDRAWAL",
            trade_date=date(2026, 1, 5),
            amount=Decimal("15000"),  # Exceeds 10,000
        ),
    ]

    with pytest.raises(LedgerValidationError, match="Insufficient cash for withdrawal"):
        replay_ledger(txs)


def test_reconciliation_report_matching_and_discrepancy() -> None:
    """Reconciliation report must detect exact matches and flag discrepancies cleanly."""
    state = LedgerState(
        cash=Decimal("100000.00"),
        holdings={
            "TCS": DerivedHolding(
                symbol="TCS",
                quantity=Decimal("50"),
                average_cost=Decimal("3000.00"),
                invested_cost=Decimal("150000.00"),
                market_price=Decimal("3000.00"),
                market_value=Decimal("150000.00"),
                unrealized_pnl=Decimal("0.00"),
                unrealized_pnl_percent=Decimal("0.00"),
                weight_percent=Decimal("60.00"),
                realized_pnl=Decimal("0"),
            ),
        },
        realized_pnl=Decimal("0"),
        total_fees=Decimal("0"),
        total_dividends=Decimal("0"),
        total_deposits=Decimal("250000.00"),
        total_withdrawals=Decimal("0"),
        net_deposits=Decimal("250000.00"),
    )

    # 1. Matching displayed balances
    report_ok = reconcile_ledger(
        state,
        displayed_cash=Decimal("100000.00"),
        displayed_holdings={"TCS": Decimal("50")},
    )
    assert report_ok.is_reconciled is True
    assert len(report_ok.discrepancies) == 0

    # 2. Cash mismatch
    report_cash_mismatch = reconcile_ledger(
        state,
        displayed_cash=Decimal("95000.00"),
        displayed_holdings={"TCS": Decimal("50")},
    )
    assert report_cash_mismatch.is_reconciled is False
    assert any("Cash mismatch" in d for d in report_cash_mismatch.discrepancies)

    # 3. Holding quantity mismatch
    report_qty_mismatch = reconcile_ledger(
        state,
        displayed_cash=Decimal("100000.00"),
        displayed_holdings={"TCS": Decimal("40")},
    )
    assert report_qty_mismatch.is_reconciled is False
    assert any("Quantity mismatch for TCS" in d for d in report_qty_mismatch.discrepancies)

    # 4. Missing holding
    report_missing = reconcile_ledger(
        state,
        displayed_cash=Decimal("100000.00"),
        displayed_holdings={"INFY": Decimal("10")},
    )
    assert report_missing.is_reconciled is False
    assert len(report_missing.discrepancies) >= 2


def test_csv_import_parse_and_export_lifecycle() -> None:
    """Verify CSV import with column aliases, error checking, and sanitized export."""
    csv_input = """date,type,symbol,quantity,price,amount,fees,notes
2026-01-01,DEPOSIT,,,,100000.00,,Initial deposit
2026-01-05,BUY,TCS,10,3200.00,,15.00,Long-term allocation
2026-01-10,DIVIDEND,TCS,,,500.00,,Q3 Dividend
"""
    txs, errors = parse_csv_transactions(csv_input)
    assert len(errors) == 0
    assert len(txs) == 3
    assert txs[0].transaction_type == "DEPOSIT"
    assert txs[1].transaction_type == "BUY"
    assert txs[1].symbol == "TCS"
    assert txs[1].quantity == Decimal("10")
    assert txs[2].transaction_type == "DIVIDEND"
    assert txs[2].amount == Decimal("500.00")

    # Export to CSV
    exported = export_csv_transactions(txs)
    assert "trade_date,transaction_type,symbol" in exported
    assert "TCS" in exported
    assert "2026-01-01" in exported


def test_csv_import_formula_injection_rejection() -> None:
    """CSV containing formula cells (=, +, -, @) must be blocked with row-level error."""
    csv_malicious = """date,type,symbol,quantity,price,notes
2026-01-01,DEPOSIT,,,100000.00,=cmd|' /C calc'!A0
"""
    txs, errors = parse_csv_transactions(csv_malicious)
    assert len(txs) == 0
    assert len(errors) == 1
    assert "formula injection" in errors[0].lower()
