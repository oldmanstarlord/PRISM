"""Weighted-Average Cost (WAC) transaction ledger accounting engine.

Transactions are the single source of truth; holdings, cash balance, and P&L
are strictly derived. Manual stock splits and bonuses are unsupported to prevent
synthetic drift.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from uuid import uuid4

TransactionType = Literal["BUY", "SELL", "FEES", "DIVIDEND", "DEPOSIT", "WITHDRAWAL"]
VALID_TRANSACTION_TYPES: set[TransactionType] = {
    "BUY",
    "SELL",
    "FEES",
    "DIVIDEND",
    "DEPOSIT",
    "WITHDRAWAL",
}

FORMULA_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class LedgerValidationError(ValueError):
    """Raised when a transaction violates ledger integrity or accounting rules."""


class FormulaInjectionError(LedgerValidationError):
    """Raised when CSV cells contain potential spreadsheet execution formulas."""


@dataclass(frozen=True, slots=True)
class LedgerTransactionInput:
    id: str
    transaction_type: TransactionType
    trade_date: date
    symbol: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal | None = None
    fees: Decimal = Decimal("0")
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class DerivedHolding:
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    invested_cost: Decimal
    market_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None
    weight_percent: Decimal | None
    realized_pnl: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": float(self.quantity),
            "average_cost": float(self.average_cost),
            "invested_cost": float(self.invested_cost),
            "market_price": (float(self.market_price) if self.market_price is not None else None),
            "market_value": (float(self.market_value) if self.market_value is not None else None),
            "unrealized_pnl": (
                float(self.unrealized_pnl) if self.unrealized_pnl is not None else None
            ),
            "unrealized_pnl_percent": (
                float(self.unrealized_pnl_percent)
                if self.unrealized_pnl_percent is not None
                else None
            ),
            "weight_percent": (
                float(self.weight_percent) if self.weight_percent is not None else None
            ),
            "realized_pnl": float(self.realized_pnl),
        }


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    is_reconciled: bool
    derived_cash: Decimal
    derived_invested_cost: Decimal
    derived_holdings_count: int
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_net_deposits: Decimal
    total_dividends: Decimal
    total_fees: Decimal
    discrepancies: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_reconciled": self.is_reconciled,
            "derived_cash": float(self.derived_cash),
            "derived_invested_cost": float(self.derived_invested_cost),
            "derived_holdings_count": self.derived_holdings_count,
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
            "total_net_deposits": float(self.total_net_deposits),
            "total_dividends": float(self.total_dividends),
            "total_fees": float(self.total_fees),
            "discrepancies": list(self.discrepancies),
        }


@dataclass(slots=True)
class LedgerState:
    cash: Decimal = Decimal("0")
    total_deposits: Decimal = Decimal("0")
    total_withdrawals: Decimal = Decimal("0")
    net_deposits: Decimal = Decimal("0")
    total_dividends: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    holdings: dict[str, DerivedHolding] = field(default_factory=dict)
    processed_transactions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_invested_cost(self) -> Decimal:
        return sum((h.invested_cost for h in self.holdings.values()), Decimal("0"))

    def total_market_value(self) -> Decimal | None:
        values = [h.market_value for h in self.holdings.values() if h.market_value is not None]
        if len(values) != len(self.holdings):
            return None
        return sum(values, Decimal("0"))

    def total_portfolio_value(self) -> Decimal | None:
        eq_val = self.total_market_value()
        if eq_val is None:
            return None
        return self.cash + eq_val

    def to_dict(self) -> dict[str, Any]:
        tot_mkt = self.total_market_value()
        tot_port = self.total_portfolio_value()
        return {
            "cash": float(self.cash),
            "total_deposits": float(self.total_deposits),
            "total_withdrawals": float(self.total_withdrawals),
            "net_deposits": float(self.net_deposits),
            "total_dividends": float(self.total_dividends),
            "total_fees": float(self.total_fees),
            "realized_pnl": float(self.realized_pnl),
            "total_invested_cost": float(self.total_invested_cost),
            "total_market_value": float(tot_mkt) if tot_mkt is not None else None,
            "total_portfolio_value": float(tot_port) if tot_port is not None else None,
            "holdings": {sym: h.to_dict() for sym, h in self.holdings.items()},
            "transaction_count": len(self.processed_transactions),
        }


def check_formula_injection(value: str) -> None:
    """Validate that text fields do not begin with executable spreadsheet formula characters."""
    if not value:
        return
    stripped = value.strip()
    if value.startswith(FORMULA_INJECTION_PREFIXES) or (
        stripped and stripped.startswith(FORMULA_INJECTION_PREFIXES)
    ):
        raise FormulaInjectionError(
            f"Prohibited spreadsheet formula cell detected: '{value[:12]}...'. "
            "Leading characters (=, +, -, @) are rejected to prevent formula injection."
        )


def validate_transaction_input(
    tx: LedgerTransactionInput,
    as_of: date | None = None,
    active_symbols: set[str] | None = None,
) -> None:
    """Perform deterministic validation on a single transaction input."""
    if tx.transaction_type not in VALID_TRANSACTION_TYPES:
        valid_types_str = sorted(VALID_TRANSACTION_TYPES)
        raise LedgerValidationError(
            f"Invalid transaction type: '{tx.transaction_type}'. Must be one of {valid_types_str}"
        )

    cutoff = as_of or date.today()
    if tx.trade_date > cutoff:
        raise LedgerValidationError(
            f"Transaction date {tx.trade_date} is in the future relative to cutoff {cutoff}."
        )

    if tx.fees < Decimal("0"):
        raise LedgerValidationError(f"Fees cannot be negative: received {tx.fees}")

    if tx.notes:
        check_formula_injection(tx.notes)

    if tx.symbol:
        check_formula_injection(tx.symbol)
        clean_sym = tx.symbol.strip().upper()
        if not clean_sym:
            raise LedgerValidationError("Symbol cannot be empty.")
        if active_symbols is not None and clean_sym not in active_symbols:
            raise LedgerValidationError(f"Symbol '{clean_sym}' is outside the authorized universe.")

    if tx.transaction_type in ("BUY", "SELL"):
        if not tx.symbol:
            raise LedgerValidationError(
                f"Symbol is required for {tx.transaction_type} transactions."
            )
        if tx.quantity is None or tx.quantity <= Decimal("0"):
            raise LedgerValidationError(
                f"Quantity must be strictly positive for {tx.transaction_type}: "
                f"received {tx.quantity}"
            )
        if tx.price is None or tx.price <= Decimal("0"):
            raise LedgerValidationError(
                f"Price must be strictly positive for {tx.transaction_type}: received {tx.price}"
            )

    elif tx.transaction_type in ("DEPOSIT", "WITHDRAWAL"):
        if tx.amount is None or tx.amount <= Decimal("0"):
            raise LedgerValidationError(
                f"Amount must be strictly positive for {tx.transaction_type}: received {tx.amount}"
            )

    elif tx.transaction_type == "DIVIDEND":
        if tx.amount is None or tx.amount <= Decimal("0"):
            raise LedgerValidationError(
                f"Dividend amount must be strictly positive: received {tx.amount}"
            )

    elif tx.transaction_type == "FEES":
        if tx.amount is None or tx.amount <= Decimal("0"):
            raise LedgerValidationError(
                f"Standalone fee amount must be strictly positive: received {tx.amount}"
            )


def replay_ledger(
    transactions: list[LedgerTransactionInput],
    market_prices: dict[str, Decimal] | None = None,
    as_of: date | None = None,
    active_symbols: set[str] | None = None,
) -> LedgerState:
    """Replay transactions chronologically under Weighted-Average Cost basis.

    Transactions are sorted by trade_date, then original order.
    The operation is strictly atomic: any invalid transaction raises an exception
    and produces no partial mutations.
    """
    seen_ids: set[str] = set()
    for tx in transactions:
        if tx.id in seen_ids:
            raise LedgerValidationError(f"Duplicate transaction ID detected: {tx.id}")
        seen_ids.add(tx.id)
        validate_transaction_input(tx, as_of=as_of, active_symbols=active_symbols)

    # Sort deterministically
    sorted_txs = sorted(transactions, key=lambda t: (t.trade_date, t.id))

    # Mutable tracking structures
    cash = Decimal("0")
    total_deposits = Decimal("0")
    total_withdrawals = Decimal("0")
    net_deposits = Decimal("0")
    total_dividends = Decimal("0")
    total_fees = Decimal("0")
    total_realized_pnl = Decimal("0")

    # symbol -> {quantity, invested_cost, realized_pnl}
    holdings_track: dict[str, dict[str, Decimal]] = {}
    processed: list[dict[str, Any]] = []

    for tx in sorted_txs:
        sym = tx.symbol.strip().upper() if tx.symbol else None

        if tx.transaction_type == "DEPOSIT":
            amount = tx.amount or Decimal("0")
            cash += amount
            total_deposits += amount
            net_deposits += amount
            processed.append(
                {
                    "id": tx.id,
                    "type": "DEPOSIT",
                    "date": tx.trade_date.isoformat(),
                    "amount": float(amount),
                    "cash_after": float(cash),
                }
            )

        elif tx.transaction_type == "WITHDRAWAL":
            amount = tx.amount or Decimal("0")
            if amount > cash:
                raise LedgerValidationError(
                    f"Insufficient cash for withdrawal of ₹{amount:,.2f}; "
                    f"available cash is ₹{cash:,.2f}."
                )
            cash -= amount
            total_withdrawals += amount
            net_deposits -= amount
            processed.append(
                {
                    "id": tx.id,
                    "type": "WITHDRAWAL",
                    "date": tx.trade_date.isoformat(),
                    "amount": float(amount),
                    "cash_after": float(cash),
                }
            )

        elif tx.transaction_type == "FEES":
            fee_amt = tx.amount or Decimal("0")
            cash -= fee_amt
            total_fees += fee_amt
            processed.append(
                {
                    "id": tx.id,
                    "type": "FEES",
                    "date": tx.trade_date.isoformat(),
                    "amount": float(fee_amt),
                    "cash_after": float(cash),
                }
            )

        elif tx.transaction_type == "DIVIDEND":
            div_amt = tx.amount or Decimal("0")
            cash += div_amt
            total_dividends += div_amt
            processed.append(
                {
                    "id": tx.id,
                    "type": "DIVIDEND",
                    "symbol": sym,
                    "date": tx.trade_date.isoformat(),
                    "amount": float(div_amt),
                    "cash_after": float(cash),
                }
            )

        elif tx.transaction_type == "BUY":
            assert sym is not None
            qty = tx.quantity or Decimal("0")
            px = tx.price or Decimal("0")
            fees = tx.fees
            gross_outlay = qty * px
            total_outlay = gross_outlay + fees

            cash -= total_outlay
            total_fees += fees

            pos = holdings_track.setdefault(
                sym,
                {
                    "quantity": Decimal("0"),
                    "invested_cost": Decimal("0"),
                    "realized_pnl": Decimal("0"),
                },
            )

            new_qty = pos["quantity"] + qty
            new_cost = pos["invested_cost"] + total_outlay
            pos["quantity"] = new_qty
            pos["invested_cost"] = new_cost

            avg_px = new_cost / new_qty if new_qty > 0 else Decimal("0")

            processed.append(
                {
                    "id": tx.id,
                    "type": "BUY",
                    "symbol": sym,
                    "date": tx.trade_date.isoformat(),
                    "quantity": float(qty),
                    "price": float(px),
                    "fees": float(fees),
                    "total_outlay": float(total_outlay),
                    "cost_basis_after": float(avg_px),
                    "cash_after": float(cash),
                }
            )

        elif tx.transaction_type == "SELL":
            assert sym is not None
            qty = tx.quantity or Decimal("0")
            px = tx.price or Decimal("0")
            fees = tx.fees

            pos_opt = holdings_track.get(sym)
            held_qty = pos_opt["quantity"] if pos_opt else Decimal("0")

            if qty > held_qty:
                raise LedgerValidationError(
                    f"Cannot sell {qty} shares of {sym}; only {held_qty} shares currently held."
                )

            assert pos_opt is not None
            pos = pos_opt
            avg_px = pos["invested_cost"] / pos["quantity"] if pos["quantity"] > 0 else Decimal("0")
            cost_basis_sold = qty * avg_px
            gross_proceeds = qty * px
            net_proceeds = gross_proceeds - fees

            realized = net_proceeds - cost_basis_sold

            cash += net_proceeds
            total_fees += fees
            total_realized_pnl += realized
            pos["realized_pnl"] += realized

            new_qty = held_qty - qty
            if new_qty == Decimal("0"):
                new_cost = Decimal("0")
            else:
                new_cost = pos["invested_cost"] - cost_basis_sold

            pos["quantity"] = new_qty
            pos["invested_cost"] = new_cost

            processed.append(
                {
                    "id": tx.id,
                    "type": "SELL",
                    "symbol": sym,
                    "date": tx.trade_date.isoformat(),
                    "quantity": float(qty),
                    "price": float(px),
                    "fees": float(fees),
                    "net_proceeds": float(net_proceeds),
                    "realized_pnl": float(realized),
                    "cash_after": float(cash),
                }
            )

    # Build final derived holdings
    final_holdings: dict[str, DerivedHolding] = {}
    tot_equity_val = Decimal("0")

    # Compute total market value for weight calculations
    if market_prices:
        for sym, pos in holdings_track.items():
            if pos["quantity"] > Decimal("0"):
                mkt_px = market_prices.get(sym)
                if mkt_px is not None:
                    tot_equity_val += pos["quantity"] * mkt_px

    for sym, pos in holdings_track.items():
        qty = pos["quantity"]
        if qty <= Decimal("0"):
            continue

        cost = pos["invested_cost"]
        avg_cost = cost / qty if qty > 0 else Decimal("0")
        mkt_px = market_prices.get(sym) if market_prices else None
        mkt_val = (qty * mkt_px) if mkt_px is not None else None

        unrealized = (mkt_val - cost) if mkt_val is not None else None
        unrealized_pct = (
            ((mkt_px - avg_cost) / avg_cost * Decimal("100"))
            if (mkt_px is not None and avg_cost > 0)
            else None
        )
        weight_pct = (
            (mkt_val / tot_equity_val * Decimal("100"))
            if (mkt_val is not None and tot_equity_val > 0)
            else None
        )

        final_holdings[sym] = DerivedHolding(
            symbol=sym,
            quantity=qty,
            average_cost=avg_cost,
            invested_cost=cost,
            market_price=mkt_px,
            market_value=mkt_val,
            unrealized_pnl=unrealized,
            unrealized_pnl_percent=unrealized_pct,
            weight_percent=weight_pct,
            realized_pnl=pos["realized_pnl"],
        )

    return LedgerState(
        cash=cash,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        net_deposits=net_deposits,
        total_dividends=total_dividends,
        total_fees=total_fees,
        realized_pnl=total_realized_pnl,
        holdings=final_holdings,
        processed_transactions=processed,
    )


def reconcile_ledger(
    state: LedgerState,
    displayed_cash: Decimal | None = None,
    displayed_holdings: dict[str, Decimal] | None = None,
    tolerance: Decimal = Decimal("0.01"),
) -> ReconciliationReport:
    """Compare ledger-derived holdings and cash against displayed balances."""
    discrepancies: list[str] = []

    if displayed_cash is not None:
        diff = abs(state.cash - displayed_cash)
        if diff > tolerance:
            discrepancies.append(
                f"Cash mismatch: Ledger derived ₹{state.cash:,.2f} vs displayed "
                f"₹{displayed_cash:,.2f} (diff: ₹{diff:,.2f})"
            )

    if displayed_holdings is not None:
        derived_syms = set(state.holdings.keys())
        displayed_syms = set(displayed_holdings.keys())

        missing_in_display = derived_syms - displayed_syms
        if missing_in_display:
            discrepancies.append(
                f"Holdings in ledger but missing from display: {sorted(missing_in_display)}"
            )

        missing_in_ledger = displayed_syms - derived_syms
        if missing_in_ledger:
            discrepancies.append(
                f"Holdings in display but missing from ledger: {sorted(missing_in_ledger)}"
            )

        common_syms = derived_syms.intersection(displayed_syms)
        for sym in sorted(common_syms):
            derived_q = state.holdings[sym].quantity
            disp_q = displayed_holdings[sym]
            q_diff = abs(derived_q - disp_q)
            if q_diff > Decimal("0.0001"):
                discrepancies.append(
                    f"Quantity mismatch for {sym}: Ledger {derived_q} vs display {disp_q}"
                )

    unrealized_total = sum(
        (h.unrealized_pnl for h in state.holdings.values() if h.unrealized_pnl is not None),
        Decimal("0"),
    )

    return ReconciliationReport(
        is_reconciled=len(discrepancies) == 0,
        derived_cash=state.cash,
        derived_invested_cost=state.total_invested_cost,
        derived_holdings_count=len(state.holdings),
        realized_pnl=state.realized_pnl,
        unrealized_pnl=unrealized_total,
        total_net_deposits=state.net_deposits,
        total_dividends=state.total_dividends,
        total_fees=state.total_fees,
        discrepancies=tuple(discrepancies),
    )


def parse_csv_transactions(
    csv_content: str,
    active_symbols: set[str] | None = None,
) -> tuple[list[LedgerTransactionInput], list[str]]:
    """Parse CSV text into typed transactions with column mapping and formula injection checks.

    Returns (parsed_transactions, errors). If errors is non-empty, parsing failed.
    """
    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    if not reader.fieldnames:
        return [], ["Empty CSV file or missing headers."]

    normalized_cols: dict[str, str] = {}
    for col in reader.fieldnames:
        clean = col.strip().lower().replace(" ", "_")
        normalized_cols[clean] = col

    # Check required minimum columns
    # Support flexible naming: date/trade_date, type/transaction_type,
    # symbol, quantity/qty, price, amount, fees/fee
    date_col = normalized_cols.get("date") or normalized_cols.get("trade_date")
    type_col = normalized_cols.get("type") or normalized_cols.get("transaction_type")

    if not date_col or not type_col:
        return [], [f"CSV missing mandatory headers 'date' and 'type'. Found: {reader.fieldnames}"]

    sym_col = normalized_cols.get("symbol")
    qty_col = normalized_cols.get("quantity") or normalized_cols.get("qty")
    px_col = normalized_cols.get("price")
    amt_col = normalized_cols.get("amount") or normalized_cols.get("value")
    fees_col = normalized_cols.get("fees") or normalized_cols.get("fee")
    notes_col = normalized_cols.get("notes") or normalized_cols.get("description")
    id_col = normalized_cols.get("id") or normalized_cols.get("transaction_id")

    transactions: list[LedgerTransactionInput] = []
    errors: list[str] = []

    for idx, row in enumerate(reader, start=2):
        try:
            raw_date = row.get(date_col, "").strip()
            raw_type = row.get(type_col, "").strip().upper()

            check_formula_injection(raw_date)
            check_formula_injection(raw_type)

            try:
                tx_date = date.fromisoformat(raw_date)
            except ValueError:
                errors.append(f"Row {idx}: Invalid date format '{raw_date}'. Expected YYYY-MM-DD.")
                continue

            if raw_type not in VALID_TRANSACTION_TYPES:
                types_str = sorted(VALID_TRANSACTION_TYPES)
                errors.append(f"Row {idx}: Invalid type '{raw_type}'. Valid types: {types_str}")
                continue

            tx_type = raw_type  # type: TransactionType

            raw_sym = row.get(sym_col, "").strip() if sym_col else None
            if raw_sym:
                check_formula_injection(raw_sym)
                sym = raw_sym.upper()
                if active_symbols and sym not in active_symbols:
                    errors.append(f"Row {idx}: Symbol '{sym}' is not in active universe.")
                    continue
            else:
                sym = None

            raw_qty = (row.get(qty_col) or "").strip() if qty_col else ""
            raw_px = (row.get(px_col) or "").strip() if px_col else ""
            raw_amt = (row.get(amt_col) or "").strip() if amt_col else ""
            raw_fees = (row.get(fees_col) or "").strip() if fees_col else "0"
            raw_notes_str = (row.get(notes_col) or "").strip() if notes_col else None
            raw_notes = raw_notes_str if raw_notes_str else None

            if raw_notes:
                check_formula_injection(raw_notes)

            qty = Decimal(raw_qty) if raw_qty else None
            px = Decimal(raw_px) if raw_px else None
            amt = Decimal(raw_amt) if raw_amt else None
            fees = Decimal(raw_fees) if raw_fees else Decimal("0")

            tx_id_raw = row.get(id_col, "").strip() if id_col else ""
            tx_id = tx_id_raw or f"csv-row-{idx}-{uuid4().hex[:8]}"

            tx_input = LedgerTransactionInput(
                id=tx_id,
                transaction_type=tx_type,
                trade_date=tx_date,
                symbol=sym,
                quantity=qty,
                price=px,
                amount=amt,
                fees=fees,
                notes=raw_notes,
            )
            validate_transaction_input(tx_input, active_symbols=active_symbols)
            transactions.append(tx_input)

        except (InvalidOperation, ValueError, FormulaInjectionError) as exc:
            errors.append(f"Row {idx}: {exc}")

    return transactions, errors


def export_csv_transactions(transactions: list[LedgerTransactionInput]) -> str:
    """Export transactions to sanitized CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "trade_date",
            "transaction_type",
            "symbol",
            "quantity",
            "price",
            "amount",
            "fees",
            "notes",
        ]
    )

    for tx in transactions:
        # Sanitize strings to avoid formula injection on export
        notes_clean = tx.notes or ""
        if notes_clean and notes_clean.startswith(FORMULA_INJECTION_PREFIXES):
            notes_clean = f"'{notes_clean}"

        sym_clean = tx.symbol or ""
        if sym_clean and sym_clean.startswith(FORMULA_INJECTION_PREFIXES):
            sym_clean = f"'{sym_clean}"

        writer.writerow(
            [
                tx.id,
                tx.trade_date.isoformat(),
                tx.transaction_type,
                sym_clean,
                str(tx.quantity) if tx.quantity is not None else "",
                str(tx.price) if tx.price is not None else "",
                str(tx.amount) if tx.amount is not None else "",
                str(tx.fees),
                notes_clean,
            ]
        )

    return output.getvalue()
